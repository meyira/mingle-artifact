//
// Copyright 2025 Signal Messenger, LLC
// SPDX-License-Identifier: AGPL-3.0-only
//

package main

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"

	"github.com/signalapp/keytransparency/cmd/internal/config"
	"github.com/signalapp/keytransparency/cmd/shared"
	"github.com/signalapp/keytransparency/db"
)

var (
	validAciIdentityKey2 = createDistinctValue(validAciIdentityKey1)
	validUsernameHash2   = createDistinctValue(validUsernameHash1)
	validPhoneNumber2    = "+14155550102"
)

type mockLogUpdater struct {
	mock.Mock
}

func (m *mockLogUpdater) update(ctx context.Context, within string, key, value []byte, updateHandler *KtUpdateHandler, expectedPreUpdateValue []byte) (returnedErr error) {
	m.Called(ctx, within, key, value, updateHandler, expectedPreUpdateValue)
	return nil
}

type expectedUpdateInputs struct {
	key            []byte
	value          []byte
	preUpdateValue []byte
}

var testUpdateAccountPairs = []struct {
	prev                 *account
	next                 *account
	expectedNumUpdates   int
	expectedUpdateInputs []expectedUpdateInputs
}{
	// No change
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		0,
		[]expectedUpdateInputs{},
	},
	// New registration
	{
		nil,
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		3,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.AciPrefix}, validAci1...), value: marshalValue(validAciIdentityKey1), preUpdateValue: nil},
			{key: append([]byte{shared.NumberPrefix}, []byte(validPhoneNumber1)...), value: marshalValue(validAci1), preUpdateValue: nil},
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash1...), value: marshalValue(validAci1), preUpdateValue: nil}},
	},
	// Re-registration - the server sets the old username to null but keeps it reserved for the client to reclaim
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey2, Number: validPhoneNumber1},
		2,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.AciPrefix}, validAci1...), value: marshalValue(validAciIdentityKey2), preUpdateValue: nil},
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)}},
	},
	// Re-registration - client reclaims username
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey2, Number: validPhoneNumber1},
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey2, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		1,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash1...), value: marshalValue(validAci1), preUpdateValue: nil}},
	},
	// Some re-registrations do not change the identity key
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, Number: validPhoneNumber1},
		1,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)}},
	},
	// Account deletion with username
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		nil,
		3,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.AciPrefix}, validAci1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAciIdentityKey1)},
			{key: append([]byte{shared.NumberPrefix}, []byte(validPhoneNumber1)...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)},
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)}},
	},
	// Account deletion with no username
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, Number: validPhoneNumber1},
		nil,
		2,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.AciPrefix}, validAci1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAciIdentityKey1)},
			{key: append([]byte{shared.NumberPrefix}, []byte(validPhoneNumber1)...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)}},
	},
	// Username change
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash2, Number: validPhoneNumber1},
		2,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash2...), value: marshalValue(validAci1), preUpdateValue: nil},
			{key: append([]byte{shared.UsernameHashPrefix}, validUsernameHash1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)}},
	},
	// Phone number change
	{
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber1},
		&account{ACI: validAci1, ACIIdentityKey: validAciIdentityKey1, UsernameHash: validUsernameHash1, Number: validPhoneNumber2},
		2,
		[]expectedUpdateInputs{
			{key: append([]byte{shared.NumberPrefix}, validPhoneNumber2...), value: marshalValue(validAci1), preUpdateValue: nil},
			{key: append([]byte{shared.NumberPrefix}, validPhoneNumber1...), value: tombstoneBytes, preUpdateValue: marshalValue(validAci1)}},
	},
}

func TestUpdateFromStream(t *testing.T) {
	mockConfig, _ := config.Read(mockConfigFile)
	mockTransparencyStore := db.NewMemoryTransparencyStore()
	updateRequestChannel := make(chan updateRequest)
	mockUpdateHandler := &KtUpdateHandler{
		config: mockConfig.APIConfig,
		tx:     mockTransparencyStore,
		ch:     updateRequestChannel,
	}
	state := &shardState{}

	for _, p := range testUpdateAccountPairs {
		mockUpdater := new(mockLogUpdater)

		accounts := &accountPair{Prev: p.prev, Next: p.next}
		marshaledData, err := json.Marshal(accounts)
		if err != nil {
			t.Fatalf("Unexpected error marshaling acocunt pair")
		}

		for _, pair := range p.expectedUpdateInputs {
			mockUpdater.On("update", mock.Anything, mock.Anything, pair.key, pair.value, mock.Anything, pair.preUpdateValue).Return(nil)
		}

		err = updateFromStream(context.Background(), marshaledData, state, mockUpdateHandler, mockUpdater)

		assert.NoError(t, err)
		mockUpdater.AssertNumberOfCalls(t, "update", p.expectedNumUpdates)
		mockUpdater.AssertExpectations(t)
	}
}

func TestLockACI(t *testing.T) {
	const parallel = 5

	state := &shardState{}
	defer state.lockACI([]byte("other"))()

	counter := 0
	output := make(chan int)
	for range parallel {
		go func() {
			defer state.lockACI([]byte("label"))()
			output <- counter
			time.Sleep(1 * time.Millisecond)
			counter++
		}()
	}

	for i := range parallel {
		if res := <-output; res != i {
			t.Fatal("unexpected counter read")
		}
	}
}
