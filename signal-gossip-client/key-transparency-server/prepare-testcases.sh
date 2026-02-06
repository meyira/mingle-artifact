#!/bin/bash

KT_CLIENT="go run ./cmd/kt-client"

ACI_UUID_1="90c979fd-eab4-4a08-b6da-69dedeab9b29"

PUBLIC_KEY_1=$(openssl rand -base64 32)

E164_NUMBER_1="+15550001234"

echo Client 1: $E164_NUMBER_1
echo "--> ACI UUID: $ACI_UUID_1" 
echo "--> Publ Key: $PUBLIC_KEY_1"
echo "==========================================="

read -r 

echo "Obtaining Distinguished Tree Head (DTH)..."

$KT_CLIENT distinguished

echo "==========================================="

echo "Press any key to insert two entries to the tree..."
read -r

$KT_CLIENT update aci "$ACI_UUID_1" "$PUBLIC_KEY_1"
# $KT_CLIENT update e164 "$E164_NUMBER_1" "$ACI_UUID_1"
