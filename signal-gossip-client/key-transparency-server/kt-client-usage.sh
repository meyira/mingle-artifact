#!/bin/bash

KT_CLIENT="go run ./cmd/kt-client"

ACI_UUID_1=$(uuidgen)
ACI_UUID_2=$(uuidgen)

PUBLIC_KEY_1=$(openssl rand -base64 32)
PUBLIC_KEY_2=$(openssl rand -base64 32)

E164_NUMBER_1="+15550001234"
E164_NUMBER_2="+15550005678"

echo Client 1: $E164_NUMBER_1
echo "--> ACI UUID: $ACI_UUID_1" 
echo "--> Publ Key: $PUBLIC_KEY_1"
echo Client 2: $E164_NUMBER_2
echo "--> ACI UUID: $ACI_UUID_2" 
echo "--> Publ Key: $PUBLIC_KEY_2"
echo "No UAK is needed, (and neither the phone number...) "
echo "==========================================="

read -r 

echo "Obtaining Distinguished Tree Head (DTH)..."

$KT_CLIENT distinguished

echo "==========================================="
read -r 

echo "Obtaining Distinguished Tree Head (DTH), and pretending as if my last known DTH was 20..."
echo "POTENTIAL BUG: Providing a last known DTH count still yields no Consistency Proofs..."

$KT_CLIENT -last 20 distinguished

echo "==========================================="

echo "Press any key to insert two entries to the tree..."
read -r

$KT_CLIENT update aci "$ACI_UUID_1" "$PUBLIC_KEY_1"
# $KT_CLIENT update e164 "$E164_NUMBER_1" "$ACI_UUID_1"
$KT_CLIENT update aci "$ACI_UUID_2" "$PUBLIC_KEY_2"
# $KT_CLIENT update e164 "$E164_NUMBER_2" "$ACI_UUID_2"
echo "==========================================="

echo "Press any key to get the DTH"
read -r

$KT_CLIENT distinguished
echo "==========================================="

echo "Press any key to search for the first E164"
read -r

$KT_CLIENT search "$ACI_UUID_1" "$PUBLIC_KEY_1"
echo "==========================================="


echo "Press any key to search for the second E164"
read -r
echo "==========================================="

$KT_CLIENT search "$ACI_UUID_2" "$PUBLIC_KEY_2"
echo "==========================================="

PUBLIC_KEY_FAKE=$(openssl rand -base64 32)

echo "Assume we got a fake public key ($PUBLIC_KEY_FAKE) piggy-backed and we check it..."
read -r

# In this case, it would fail
$KT_CLIENT search "$ACI_UUID_2" "$PUBLIC_KEY_FAKE"

echo But there is one thing we want to test: What if the server lies and provides me an entry that is apparently off?
echo Then we would take the included DTH and the search proof and check it ourselves
echo To be continued...

echo "==========================================="

echo "Monitoring the key with regard to User 1..."
read -r
$KT_CLIENT -config my-config.yaml monitor "$ACI_UUID_1" "$PUBLIC_KEY_1"


echo "Normally, I would need to save the key, wait a little and do a monitor again to get a consistency proof..."
