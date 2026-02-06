//
// Copyright 2024 Signal Messenger, LLC.
// SPDX-License-Identifier: AGPL-3.0-only
//

use std::collections::HashMap;
use crate::support::*;
use crate::*;
use itertools::Itertools;
use libsignal_bridge_macros::{bridge_fn, bridge_io};
use libsignal_bridge_types::net::chat::UnauthenticatedChatConnection;
pub use libsignal_bridge_types::net::{Environment, TokioAsyncContext};
use libsignal_bridge_types::support::AsType;
use libsignal_core::{Aci, E164};
use libsignal_keytrans::verify::{verify_distinguished, verify_monitor, verify_search};
use libsignal_keytrans::{vrf, AccountData, DeploymentMode, FullSearchResponse, FullTreeHead, LastTreeHead, LocalStateUpdate, MonitorContext, MonitorRequest, MonitorResponse, PublicConfig, SearchContext, SearchResponse, SlimSearchRequest, StoredAccountData, StoredTreeHead, TreeHead, VerifyingKey, Versioned};
use libsignal_net_chat::api::keytrans::{
    monitor_and_search, Error, KeyTransparencyClient, MaybePartial, MonitorMode,
    SearchKey, UnauthenticatedChatApi as _, UsernameHash,
};
use libsignal_net_chat::api::RequestError;
use libsignal_protocol::PublicKey;
use prost::{DecodeError, Message};
use std::convert::TryFrom;
use std::time::SystemTime;
use ed25519_dalek::SigningKey;
use libsignal_core::curve::PrivateKey;

#[bridge_fn]
fn KeyTransparency_AciSearchKey(aci: Aci) -> Vec<u8> {
    aci.as_search_key()
}

#[bridge_fn]
fn KeyTransparency_E164SearchKey(e164: E164) -> Vec<u8> {
    e164.as_search_key()
}

#[bridge_fn]
fn KeyTransparency_UsernameHashSearchKey(hash: &[u8]) -> Vec<u8> {
    UsernameHash::from_slice(hash).as_search_key()
}

#[bridge_fn]
fn Verify_Distinguished(
    fth_bytes: Option<Box<[u8]>>,
    trusted_root_bytes: Option<Box<[u8]>>,
    trusted_tree_size: u64,
) -> Result<Vec<u8>, RequestError<Error>> {

    let fth_bytes = fth_bytes.ok_or(invalid_request("No FTH bytes provided"))?;
    // Should work, as the protobuf definitons are the same: wire.proto (Libsignal) == transparecy.proto (KT Server)
    let fth = FullTreeHead::decode(&*fth_bytes)
        .map_err(|e| invalid_request("Protobuf decode failed: {}"))?;

    // FIXME bugfix
    let last_trusted = if let Some(root_bytes) = trusted_root_bytes {
        let root_hash: [u8; 32] = (*root_bytes).try_into()
            .map_err(|_| invalid_request("Invalid root hash length (must be 32)"))?;

        Some((
            TreeHead {
                tree_size: trusted_tree_size,
                timestamp: 0,
                signatures: vec![],
            },
            root_hash
        ))
    } else {
        None
    };

    // Calling verification method. This has already been implemented by Signal
    verify_distinguished(&fth, last_trusted.as_ref(), last_trusted.as_ref().unwrap_or(&LastTreeHead::default()))
        .map_err(|e| invalid_request("CRYPTO VERIFICATION FAILED: {:?}"))?;

    // Rule of thumb: if nothing is thrown, the objects shall be ok
    Ok(vec![])
}

#[bridge_fn]
fn Verify_Search(
    aci_key: Option<Box<[u8]>>,   // only the ACI. converted to vec<u8>
    full_search_response_bytes: Option<Box<[u8]>>, // to be unmarshalled here and separated into SearchResponses
    lth_bytes: Option<Box<[u8]>>,   // Type LastTreeHead, contains a TreeHead (protobuf) and a TreeRoot
    ldth_bytes: Option<Box<[u8]>>,  // Type LastTreeHead, contains a TreeHead (protobuf) and a TreeRoot
    md_bytes: Option<Box<[u8]>>, // will certainly set it to None or null or whatever its called in Rust
    force_monitor: bool,
) -> Result<Vec<u8>, RequestError<Error>> {
    //     req: SlimSearchRequest,  <-- I expect search_key to be the ACI. only search_key needed for init.
    //     res: FullSearchResponse, <-- SearchResponse: FullTreeHead and up to 3 CondensedTreeSearchResponse
    // While FullSearchResponse only has one FullTreeHead and one CondensedTreeSearchResponse.
    // Hence, its better to have one FullSearchResponse sent over and construct the SearchResponses here

    //     context: SearchContext,  <-- contains the last tree head, distinguished tree head and MonitoringData
    // Provide it via JNI and construct the object here
    //     force_monitor: bool,     <-- i will set it to false, I CBA researching it tbh
    //     now: SystemTime,         <-- i will set it to the current time.
    // -> Result<SearchStateUpdate>
    let config = get_hardcoded_config()
        .map_err(|e| invalid_response(format!("the config is invalid: {}", e).to_string()))?;

    let aci_vec = aci_key.ok_or(invalid_request("ACI is invalid"))?.to_vec();
    let req = SlimSearchRequest::new(aci_vec);

    let sr_bytes = full_search_response_bytes
        .ok_or(invalid_request("FSR is *****"))?;

    let proto_res = SearchResponse::decode(&*sr_bytes)
        .map_err(|e| invalid_request("Protobuf Decode Failed: {}"))?;

    // Verify SearchResponses on its own

    let tree_head_ref = proto_res.tree_head.as_ref()
        .ok_or(invalid_request("Missing TreeHead in SearchResponse"))?;

    // Creating up to 3 FullSearchResponses out of the SearchResponse
    let full_res = FullSearchResponse {
        condensed: proto_res.aci.clone()
            .ok_or(invalid_response("****!".to_string()))
            .map_err(|e| invalid_response("****!".to_string()))?,
        tree_head: tree_head_ref,
    };

    let last_th = None;
    // let last_th: Option<LastTreeHead> = if let Some(bytes) = lth_bytes {
    //     let proto_lth = LastTreeHead::decode(&*bytes).map_err(|_| invalid_request("LTH Fail"))?;
    //     let tree_root: [u8; 32] = proto_lth.tree_root.try_into().map_err(|_| invalid_request("Bad Root"))?;
    //     let th = proto_lth.tree_head.ok_or(invalid_request("Missing LTH TreeHead"))?;
    //     Some((th, tree_root))
    // } else {
    //     None
    // };

    let context = SearchContext {
        last_tree_head: last_th,
        last_distinguished_tree_head: None,
        data: None,
        ..Default::default()
    };

    let now = SystemTime::now();
    // Call verify_search for each SearchResult entry
    verify_search(&config, req, full_res, context, false, now);
    Ok(vec![])
}

fn get_hardcoded_config() -> Result<PublicConfig, String> {
    // absolute cringe to have private keys here to derivate public keys
    // in a normal setting we have normal public keys here
    let vrf_priv_hex = "05f9d16238ed0bc318807edd76f3db59399ecf0daf8e57b6fb628fdeff863087";
    let sig_priv_hex = "2964fbf535701b0adea21afb1b97294cb71c70d3eeadd656297a13af2d31d586";

    let vrf_seed_vec = hex::decode(vrf_priv_hex).map_err(|_| "Hex decode failed")?;
    let vrf_seed_bytes: [u8; 32] = vrf_seed_vec.try_into().map_err(|_| "Bad len")?;

    let vrf_private = SigningKey::from_bytes(&vrf_seed_bytes);
    let vrf_public = vrf_private.verifying_key();

    let vrf_key = vrf::PublicKey::try_from(vrf_public.to_bytes())
        .map_err(|_| "Derived VRF PubKey invalid")?;

    let sig_seed_vec = hex::decode(sig_priv_hex).map_err(|_| "Hex decode failed")?;
    let sig_seed_bytes: [u8; 32] = sig_seed_vec.try_into().map_err(|_| "Bad len")?;

    let sig_private = SigningKey::from_bytes(&sig_seed_bytes);
    let signature_key = sig_private.verifying_key();

    Ok(PublicConfig {
        mode: DeploymentMode::ContactMonitoring,
        signature_key,
        vrf_key,
    })
}

#[bridge_fn]
fn Verify_And_Get_Commitment_Index(
    userIdBytes: Option<Box<[u8]>>,
    vrfProofBytes: Option<Box<[u8]>>
) -> Result<Vec<u8>, RequestError<Error>> {
    let config = get_hardcoded_config()
        .map_err(|e| invalid_response(format!("config invalid: {}", e)))?;

    let user_id = userIdBytes.ok_or_else(|| invalid_response("User ID missing".to_string()))?;
    let proof_vec = vrfProofBytes.ok_or_else(|| invalid_response("VRF Proof missing".to_string()))?;

    let proof_array: [u8; 80] = proof_vec.as_ref().try_into()
        .map_err(|_| invalid_response("VRF Proof must be exactly 80 bytes".to_string()))?;

    let mut message = Vec::with_capacity(1 + user_id.len());
    message.push(b'a');
    message.extend_from_slice(&user_id);

    let commitment_index = config.vrf_key.proof_to_hash(&message, &proof_array)
        .map_err(|_| invalid_response("VRF Verification failed".to_string()))?;

    Ok(commitment_index.to_vec())
}

#[bridge_fn]
fn Verify_Monitor(
    req: Option<Box<[u8]>>,
    res: Option<Box<[u8]>>,
    last_tree_head: Option<Box<[u8]>>,
    last_distinguished_tree_head: Option<Box<[u8]>>,
    now: u64
) -> Result<Vec<u8>, RequestError<Error>> {
    // req: ByteArray?,
    // res: ByteArray?,
    // lastTreeHead: ByteArray?,
    // last_distinguished_tree_head: ByteArray?,
    // data: ByteArray?, now: Long

    // config: &'a PublicConfig,
    // req: &'a MonitorRequest (already converted on java level)
    // res: &'a MonitorResponse (already converted on java level)
    // context: MonitorContext (to be built together)
    // now: SystemTime, (i will ignore it and use my own time for now)

    let config = get_hardcoded_config()
        .map_err(|e| invalid_request("Error while loading config"))?;

    let req_bytes = req.ok_or(invalid_request("Request is invalid"))?;
    let restored_req = MonitorRequest::decode(&*req_bytes)
        .map_err(|e| invalid_request("Req Decode failed"))?;

    let res_bytes = res.ok_or(invalid_request("Response is invalid"))?;
    let restored_res = MonitorResponse::decode(&*res_bytes)
        .map_err(|e| invalid_request("Res Decode failed"))?;

    let lth = None;
    // let lth_bytes = last_tree_head.ok_or(invalid_request("LTH is invalid"));
    // let restored_lth = LastTreeHead::try_from(&lth_bytes)
    //     .map_err(|_| "Invalid LTH")?;

    let dummy_tuple = (TreeHead::default(), [0u8; 32]);

    let actual_ldth: LastTreeHead = if let Some(bytes) = last_distinguished_tree_head {
        let stored = StoredTreeHead::decode(&*bytes)
            .map_err(|_| invalid_request("LDTH Decode Failed"))?;
        stored.into_last_tree_head().ok_or(invalid_request("LDTH Convert Failed"))?
    } else {
        dummy_tuple
    };
    // let ldth_bytes = last_distinguished_tree_head.ok_or(invalid_request("LDTH is invalid"));
    // let restored_ldth = LastTreeHead::try_from(&ldth_bytes)
    //     .map_err(|_| "Invalid LDTH")?;


    let context = MonitorContext {
        last_tree_head: lth,
        last_distinguished_tree_head: &actual_ldth,
        data: HashMap::new(), // I will not dare to do the JNI voodoo on hashmaps now...
    };

    verify_monitor(&config, &restored_req, &restored_res, context, SystemTime::now()).expect("TODO: panic message");
    Ok(vec![])
}

#[bridge_io(TokioAsyncContext)]
#[expect(clippy::too_many_arguments)]
async fn KeyTransparency_Search(
    // TODO: it is currently possible to pass an env that does not match chat
    environment: AsType<Environment, u8>,
    chat_connection: &UnauthenticatedChatConnection,
    aci: Aci,
    aci_identity_key: &PublicKey,
    e164: Option<E164>,
    unidentified_access_key: Option<Box<[u8]>>,
    username_hash: Option<Box<[u8]>>,
    account_data: Option<Box<[u8]>>,
    last_distinguished_tree_head: Box<[u8]>,
) -> Result<Vec<u8>, RequestError<Error>> {
    let username_hash = username_hash.map(UsernameHash::from);
    let config = environment.into_inner().env().keytrans_config;

    let e164_pair = make_e164_pair(e164, unidentified_access_key)?;

    let account_data = account_data.map(try_decode_account_data).transpose()?;

    let last_distinguished_tree_head = try_decode_distinguished(last_distinguished_tree_head)?;

    let maybe_partial_result = chat_connection
        .as_typed(|chat| {
            Box::pin(async move {
                let kt = KeyTransparencyClient::new(*chat, config);
                kt.search(
                    Versioned::from(&aci),
                    aci_identity_key,
                    e164_pair.map(Versioned::from),
                    username_hash.map(Versioned::from),
                    account_data,
                    &last_distinguished_tree_head,
                )
                .await
            })
        })
        .await?;

    maybe_partial_to_serialized_account_data(maybe_partial_result)
}

#[bridge_io(TokioAsyncContext)]
#[expect(clippy::too_many_arguments)]
async fn KeyTransparency_Monitor(
    // TODO: it is currently possible to pass an env that does not match chat
    environment: AsType<Environment, u8>,
    chat_connection: &UnauthenticatedChatConnection,
    aci: Aci,
    aci_identity_key: &PublicKey,
    e164: Option<E164>,
    unidentified_access_key: Option<Box<[u8]>>,
    username_hash: Option<Box<[u8]>>,
    // Bridging this as optional even though it is required because it is
    // simpler to produce an error once here than on all platforms.
    account_data: Option<Box<[u8]>>,
    last_distinguished_tree_head: Box<[u8]>,
    is_self_monitor: bool,
) -> Result<Vec<u8>, RequestError<Error>> {
    let username_hash = username_hash.map(UsernameHash::from);

    let Some(account_data) = account_data else {
        return Err(invalid_request("account data not found in store"));
    };

    let account_data = try_decode_account_data(account_data)?;

    let last_distinguished_tree_head = try_decode_distinguished(last_distinguished_tree_head)?;

    let config = environment.into_inner().env().keytrans_config;

    let mode = if is_self_monitor {
        MonitorMode::MonitorSelf
    } else {
        MonitorMode::MonitorOther
    };

    let e164_pair = make_e164_pair(e164, unidentified_access_key)?;

    let maybe_partial_result = chat_connection
        .as_typed(|chat| {
            Box::pin(async move {
                let kt = KeyTransparencyClient::new(*chat, config);
                monitor_and_search(
                    &kt,
                    &aci,
                    aci_identity_key,
                    e164_pair,
                    username_hash,
                    account_data,
                    &last_distinguished_tree_head,
                    mode,
                )
                .await
            })
        })
        .await?;

    maybe_partial_to_serialized_account_data(maybe_partial_result)
}

#[bridge_io(TokioAsyncContext)]
async fn KeyTransparency_Distinguished(
    // TODO: it is currently possible to pass an env that does not match chat
    environment: AsType<Environment, u8>,
    chat_connection: &UnauthenticatedChatConnection,
    last_distinguished_tree_head: Option<Box<[u8]>>,
) -> Result<Vec<u8>, RequestError<Error>> {
    let config = environment.into_inner().env().keytrans_config;

    let known_distinguished = last_distinguished_tree_head
        .map(try_decode)
        .transpose()
        .map_err(|_| invalid_request("could not decode account data"))?
        .and_then(|stored: StoredTreeHead| stored.into_last_tree_head());

    let LocalStateUpdate {
        tree_head,
        tree_root,
        monitoring_data: _,
    } = chat_connection
        .as_typed(|chat| {
            Box::pin(async move {
                let kt = KeyTransparencyClient::new(*chat, config);
                kt.distinguished(known_distinguished).await
            })
        })
        .await?;

    let updated_distinguished = StoredTreeHead::from((tree_head, tree_root));
    let serialized = updated_distinguished.encode_to_vec();
    Ok(serialized)
}

fn invalid_request(msg: &'static str) -> RequestError<Error> {
    RequestError::Other(Error::InvalidRequest(msg))
}

fn invalid_response(msg: String) -> RequestError<Error> {
    RequestError::Other(Error::InvalidResponse(msg))
}

fn make_e164_pair(
    e164: Option<E164>,
    unidentified_access_key: Option<Box<[u8]>>,
) -> Result<Option<(E164, Vec<u8>)>, RequestError<Error>> {
    match (e164, unidentified_access_key) {
        (None, None) => Ok(None),
        (Some(e164), Some(uak)) => Ok(Some((e164, uak.into_vec()))),
        (None, Some(_uak)) => Err(invalid_request("Unidentified access key without an E164")),
        (Some(_e164), None) => Err(invalid_request("E164 without unidentified access key")),
    }
}

fn try_decode<B, T>(bytes: B) -> Result<T, DecodeError>
where
    B: AsRef<[u8]>,
    T: Message + Default,
{
    T::decode(bytes.as_ref())
}

fn try_decode_account_data(bytes: Box<[u8]>) -> Result<AccountData, RequestError<Error>> {
    let stored: StoredAccountData =
        try_decode(bytes).map_err(|_| invalid_request("could not decode account data"))?;
    AccountData::try_from(stored).map_err(|err| RequestError::Other(Error::from(err)))
}

fn try_decode_distinguished(bytes: Box<[u8]>) -> Result<LastTreeHead, RequestError<Error>> {
    try_decode(bytes)
        .map(|stored: StoredTreeHead| stored.into_last_tree_head())
        .map_err(|_| invalid_request("could not decode last distinguished tree head"))?
        .ok_or(invalid_request("last distinguished tree is required"))
}

fn maybe_partial_to_serialized_account_data(
    maybe_partial: MaybePartial<AccountData>,
) -> Result<Vec<u8>, RequestError<Error>> {
    maybe_partial
        .map(|data| StoredAccountData::from(data).encode_to_vec())
        .into_result()
        .map_err(|missing| {
            invalid_response(format!(
                "Some fields are missing from the response: {}",
                missing.iter().join(", ")
            ))
        })
}
