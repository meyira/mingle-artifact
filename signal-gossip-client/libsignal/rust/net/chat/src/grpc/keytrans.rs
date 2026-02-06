// use super::GrpcServiceProvider;
// use crate::api::keytrans::{Error, MaybePartial, UsernameHash};
// use crate::api::{RequestError, Unauth};
// use libsignal_core::curve::PublicKey;
// use libsignal_core::{Aci, E164};
// use libsignal_keytrans::{AccountData, LastTreeHead, SearchStateUpdate, Versioned};
// use libsignal_net_grpc::proto::keytrans::kt_query::key_transparency_query_service_client::KeyTransparencyQueryServiceClient;
// use libsignal_net_grpc::proto::keytrans::kt_query::DistinguishedRequest;
// use prost::Message;
//
// const CUSTOM_HOST: &str = "http://10.0.2.2:8080";
//
// impl<T: GrpcServiceProvider> crate::api::keytrans::UnauthenticatedChatApiV2 for Unauth<T> {
//     async fn search(
//         &self,
//         aci: Versioned<&Aci>,
//         aci_identity_key: &PublicKey,
//         e164: Option<Versioned<(E164, Vec<u8>)>>,
//         username_hash: Option<Versioned<UsernameHash<'_>>>,
//         stored_account_data: Option<AccountData>,
//         distinguished_tree_head: &LastTreeHead,
//     ) -> Result<MaybePartial<AccountData>, RequestError<Error>> {
//         unimplemented!()
//     }
//
//     async fn distinguished(
//         &self,
//         last_distinguished: Option<LastTreeHead>,
//     ) -> Result<SearchStateUpdateV2, RequestError<Error>> {
//         // TODO replace self.service() by another connection to the local KT Server
//         let mut client = KeyTransparencyQueryServiceClient::new(self.service());
//         let request = DistinguishedRequest {
//             last: last_distinguished.map(|lth| lth.0.tree_size)
//         };
//         let response = client.distinguished(request).await
//             .map_err(|status| RequestError::Unexpected {
//                 log_safe: format!("KT Distinguished Error: {}", status)
//             })?
//             .into_inner();
//
//         Ok(SearchStateUpdateV2 { response } )
//     }
//
//     async fn monitor(
//         &self,
//         aci: &Aci,
//         e164: Option<E164>,
//         username_hash: Option<UsernameHash<'_>>,
//         account_data: AccountData,
//         last_distinguished_tree_head: &LastTreeHead,
//     ) -> Result<AccountData, RequestError<Error>> {
//         unimplemented!()
//     }
// }
//
// // impl std::fmt::Display for Redact<&'_ LookupUsernameHashRequest> {
// //     fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
// //         let Self(LookupUsernameHashRequest { username_hash }) = self;
// //         f.debug_struct("LookupUsernameHash")
// //             .field("username_hash", &RedactHex(&hex::encode(username_hash)))
// //             .finish()
// //     }
// // }
//
// #[cfg(test)]
// mod test {
//     use futures_util::FutureExt as _;
//     use test_case::test_case;
//     use tonic::transport::Endpoint;
//
//     use super::*;
//     use crate::grpc::testutil::{req, RequestValidator};
//     use libsignal_net_grpc::proto::keytrans::kt_query::{DistinguishedResponse};
//     use libsignal_net_grpc::proto::keytrans::transparency::{FullTreeHead, TreeHead};
//
//     const TEST_HOST: &str = "http://127.0.0.1:8080";
//
//     // Integration test to make sure that it works in this layer
//     #[tokio::test]
//     async fn test_distinguished_call_against_local_server() {
//         let addr = TEST_HOST;
//
//         println!("Connecting to KT Server at {}...", addr);
//
//         let channel = Endpoint::from_static(addr)
//             .connect()
//             .await
//             .expect("Failed to connect to KT Server ");
//         let mut client = KeyTransparencyQueryServiceClient::new(channel);
//
//         let request = DistinguishedRequest {
//             last: None
//         };
//
//         let response = client.distinguished(request)
//             .await;
//
//         match response {
//             Ok(resp) => {
//                 let inner = resp.into_inner();
//                 // The output here is vibe-coded
//                 println!("Tree Size: {:?}", inner.tree_head
//                     .as_ref()
//                     .and_then(|th| th.tree_head.as_ref())
//                     .map(|h| h.tree_size)
//                 );
//                 assert!(inner.tree_head.is_some(), "Should return a tree head");
//                 if let Some(full_head) = &inner.tree_head {
//                     if let Some(head) = &full_head.tree_head {
//                         for (i, sig) in head.signatures.iter().enumerate() {
//                             // 1. Auditor Public Key (als Hex)
//                             let key_hex: String = sig.auditor_public_key.iter() // Feldname checken (ggf. key_id?)
//                                 .map(|b| format!("{:02x}", b)).collect();
//
//                             // 2. Die eigentliche Signatur (als Hex)
//                             // Proto-Feld heißt meistens 'signature'
//                             let sig_hex: String = sig.signature.iter()
//                                 .map(|b| format!("{:02x}", b)).collect();
//
//                             println!("Auditor #{}:", i);
//                             println!("  🔑 Key: {}", key_hex);
//                             println!("  ✍️ Sig: {}", sig_hex);
//                         }
//
//                         // Der wichtigste Check: ROOT HASH
//                         // (Ist oft im FullTreeHead, eine Ebene drüber)
//                         if let Some(full) = &inner.tree_head {
//                             // Feldname könnte 'root_hash' oder einfach 'root' sein
//                             // let root_hex: String = full.root_hash.iter().map(|b| format!("{:02x}", b)).collect();
//                             // println!("🌳 Root Hash: {}", root_hex);
//
//                             // Falls du das Feld nicht findest, debug erst nochmal das ganze Struct:
//                             println!("FullHead Structure: {:#?}", full);
//                         }
//                     } else {
//                         println!("FullTreeHead war da, aber innerer TreeHead fehlt!");
//                     }
//                 } else {
//                     println!("Kein TreeHead in der Response!");
//                 }
//                 // End of vibe-coding
//             },
//             Err(e) => {
//                 panic!("gRPC call failed: {:?}", e);
//             }
//         }
//     }
// }
