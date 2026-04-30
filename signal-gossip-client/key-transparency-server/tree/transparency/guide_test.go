//
// Copyright 2025 Signal Messenger, LLC
// SPDX-License-Identifier: AGPL-3.0-only
//

package transparency

import (
	"slices"
	"testing"
)

// executeGuide takes in a proofGuide, an upper and lower bound on the search space, and a target entry ID.
// It returns the implicit binary tree's search path to the target entry ID if the target exists within the bounds;
// otherwise it returns the lower bound value.
func executeGuide(guide *proofGuide, start, end, target uint64) []uint64 {
	ids := make([]uint64, 0)
	for {
		done, err := guide.done()
		if err != nil {
			panic(err)
		} else if done {
			break
		}
		id := guide.next()

		if id < start {
			panic("requested id is before start point")
		} else if id >= end {
			panic("requested id is after end point")
		}

		ids = append(ids, id)
		if id < target {
			guide.insert(id, 0)
		} else {
			guide.insert(id, 1)
		}
	}
	return ids
}

func TestMostRecentProofGuide(t *testing.T) {
	guide := mostRecentProofGuide(100, 700)
	ids := executeGuide(guide, 100, 700, 701)
	if ids[guide.final()] != 100 {
		t.Fatal("wrong result returned")
	}

	guide = mostRecentProofGuide(100, 700)
	ids = executeGuide(guide, 100, 700, 90)
	if ids[guide.final()] != 100 {
		t.Fatal("wrong result returned")
	}

	guide = mostRecentProofGuide(100, 700)
	ids = executeGuide(guide, 100, 700, 399)
	if ids[guide.final()] != 399 {
		t.Fatal("wrong result returned")
	}

	guide = mostRecentProofGuide(100, 700)
	ids = executeGuide(guide, 100, 700, 699)
	if ids[guide.final()] != 699 {
		t.Fatal("wrong result returned")
	}

	guide = mostRecentProofGuide(100, 701)
	ids = executeGuide(guide, 100, 701, 700)
	if ids[guide.final()] != 700 {
		t.Fatal("wrong result returned")
	}
}

func TestVersionProofGuide(t *testing.T) {
	guide := versionProofGuide(1, 1, 28)
	ids := executeGuide(guide, 1, 28, 17)
	if !slices.Equal([]uint64{15, 23, 19, 17, 16}, ids) {
		t.Fatal("wrong result returned")
	}

	guide = versionProofGuide(1, 1, 28)
	ids = executeGuide(guide, 1, 28, 27)
	if !slices.Equal([]uint64{15, 23, 27, 25, 26}, ids) {
		t.Fatal("wrong result returned")
	}
}
