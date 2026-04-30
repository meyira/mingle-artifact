//
// Copyright 2025 Signal Messenger, LLC
// SPDX-License-Identifier: AGPL-3.0-only
//

package prefix

import (
	"bytes"
	"crypto/rand"
	mrand "math/rand"
	"slices"
	"testing"

	"github.com/signalapp/keytransparency/db"
)

func random() []byte {
	out := make([]byte, IndexLength)
	if _, err := rand.Read(out); err != nil {
		panic(err)
	}
	return out
}

func TestPrefixTreeSearchForVersion(t *testing.T) {
	var (
		tree      = NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
		repeatKey = random()
		// The i-th value is the update position for version i of repeatKey
		versionPositions []uint64

		randomKeys [][]byte
		treeSize   uint64
	)

	for i := 0; i < 1000; i++ {
		dice := mrand.Intn(4)

		if dice == 0 && len(versionPositions) > 0 { // Search for a random version of the key
			version := uint32(mrand.Intn(len(versionPositions)))

			res, err := tree.SearchForVersion(treeSize, repeatKey, version)
			if err != nil {
				t.Fatal(err)
			} else if res.Counter != version {
				t.Fatal("unexpected value for version counter")
			} else if res.FirstUpdatePosition != versionPositions[0] {
				t.Fatal("unexpected value for first update position")
			} else if res.LatestUpdatePosition != versionPositions[version] {
				t.Fatal("unexpected value for version update position")
			}
		} else if dice == 1 && (len(randomKeys) > 0 || len(versionPositions) > 0) { // Insert a fake entry.
			_, err := tree.InsertFake(treeSize)
			if err != nil {
				t.Fatal(err)
			}
			treeSize = treeSize + 1
		} else if dice == 2 { // Insert a new index.
			randomKey := random()
			_, _, err := tree.Insert(treeSize, randomKey, make([]byte, 32), false)
			if err != nil {
				t.Fatal(err)
			}
			randomKeys = append(randomKeys, randomKey)
			treeSize = treeSize + 1
		} else if dice == 3 { // Insert repeatKey again
			_, _, err := tree.Insert(treeSize, repeatKey, make([]byte, 32), false)
			if err != nil {
				t.Fatal(err)
			}
			versionPositions = append(versionPositions, treeSize)
			treeSize = treeSize + 1
		}
	}
}

func TestPrefixTree(t *testing.T) {
	var (
		tree = NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())

		keys                 [][]byte
		ctr                  []uint32
		firstUpdatePosition  []uint64
		latestUpdatePosition []uint64

		treeSize uint64
		root     []byte
	)

	for i := 0; i < 1000; i++ {
		dice := mrand.Intn(4)

		if dice == 0 && len(keys) > 0 { // Search for an existing index.
			k := mrand.Intn(len(keys))

			res, err := tree.Search(treeSize, keys[k])
			if err != nil {
				t.Fatal(err)
			} else if err = Verify(root, keys[k], firstUpdatePosition[k], res); err != nil {
				t.Fatal(err)
			} else if res.Counter != ctr[k] {
				t.Fatal("unexpected value for version counter")
			} else if res.FirstUpdatePosition != firstUpdatePosition[k] {
				t.Fatal("unexpected value for first update position")
			} else if res.LatestUpdatePosition != latestUpdatePosition[k] {
				t.Fatal("unexpected value for latest update position")
			}
		} else if dice == 1 && len(keys) > 0 { // Insert a fake entry.
			temp, err := tree.InsertFake(treeSize)
			if err != nil {
				t.Fatal(err)
			}
			treeSize, root = treeSize+1, temp
		} else if dice == 2 { // Insert a new index.
			key := random()
			temp, _, err := tree.Insert(treeSize, key, make([]byte, 32), false)
			if err != nil {
				t.Fatal(err)
			}
			keys = append(keys, key)
			ctr = append(ctr, 0)
			firstUpdatePosition = append(firstUpdatePosition, treeSize)
			latestUpdatePosition = append(latestUpdatePosition, treeSize)
			treeSize, root = treeSize+1, temp
		} else if dice == 3 && len(keys) > 0 { // Insert an existing index.
			k := mrand.Intn(len(keys))
			temp, _, err := tree.Insert(treeSize, keys[k], make([]byte, 32), false)
			if err != nil {
				t.Fatal(err)
			}
			ctr[k] += 1
			latestUpdatePosition[k] = treeSize
			treeSize, root = treeSize+1, temp
		}
	}
}

func TestBatchSearch(t *testing.T) {
	var (
		tree      = NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
		treeSizes = []uint64{20, 50, 100, 200, 250}

		key         []byte
		roots       [][]byte
		commitments [][]byte
	)
	for treeSize := uint64(0); treeSize < 300; treeSize++ {
		temp := random()
		root, sr, err := tree.Insert(treeSize, temp, make([]byte, 32), false)
		if err != nil {
			t.Fatal(err)
		}

		if treeSize == 10 {
			key = temp
		} else if slices.Contains(treeSizes, treeSize+1) {
			roots = append(roots, root)
			commitments = append(commitments, sr.Commitment)
		}
	}

	searches := make([]*Search, 0)
	for _, treeSize := range treeSizes {
		search, err := tree.BatchSearch(treeSize, key)
		if err != nil {
			t.Fatal(err)
		}
		searches = append(searches, search)
	}
	results, err := tree.BatchExec(searches)
	if err != nil {
		t.Fatal(err)
	}
	for i, res := range results {
		if err = Verify(roots[i], key, 10, res); err != nil {
			t.Fatal(err)
		} else if res.FirstUpdatePosition != 10 {
			t.Fatal("unexpected value for first update position")
		} else if res.LatestUpdatePosition != 10 {
			t.Fatal("unexpected value for latest update position")
		} else if !bytes.Equal(res.Commitment, commitments[i]) {
			t.Fatal("unexpected value for commitment")
		}
	}
}

func randomEntry() Entry {
	return Entry{Index: random(), Commitment: random()}
}

func TestBatchInsertFakeUpdatesEmptyTree(t *testing.T) {
	// Build a set of entries to add.
	entries := make([]Entry, 0)
	for i := 0; i < 10; i++ {
		entries = append(entries, randomEntry())
	}

	tree := NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
	_, _, err := tree.BatchInsert(0, entries, true)
	if err == nil {
		t.Fatal("expected error inserting fake entries into an empty tree")
	}
}

func TestBatchInsert(t *testing.T) {
	// Build a set of entries to add.
	entries := make([]Entry, 0)
	for i := 0; i < 100; i++ {
		entries = append(entries, randomEntry())
	}
	for i := 75; i < 78; i++ {
		entries[i].Index = entries[70].Index
	}
	for i := 81; i < 84; i++ {
		entries[i].Index = entries[10].Index
	}

	// Insert into the tree in batches.
	tree1 := NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
	_, _, err := tree1.BatchInsert(0, entries[:50], false)
	if err != nil {
		t.Fatal(err)
	}
	roots, _, err := tree1.BatchInsert(50, entries[50:], false)
	if err != nil {
		t.Fatal(err)
	}
	root1 := roots[49]

	// Insert into the tree one-by-one.
	tree2 := NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
	var root2 []byte
	for i, entry := range entries {
		root2, _, err = tree2.Insert(uint64(i), entry.Index, entry.Commitment, false)
		if err != nil {
			t.Fatal(err)
		}
	}

	if !bytes.Equal(root1, root2) {
		t.Fatal("roots do not match")
	}
}

func BenchmarkInsert(b *testing.B) {
	tree := NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
	for i := 0; i < 100; i++ {
		entry := randomEntry()
		_, _, err := tree.Insert(uint64(i), entry.Index, entry.Commitment, false)
		if err != nil {
			b.Fatal(err)
		}
	}
	entries := make([]Entry, b.N)
	for i := range entries {
		entries[i] = randomEntry()
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _, err := tree.Insert(100+uint64(i), entries[i].Index, entries[i].Commitment, false)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkBatchInsert(b *testing.B) {
	const batchSize = 80

	tree := NewTree(make([]byte, 16), db.NewMemoryTransparencyStore().PrefixStore())
	for i := 0; i < 100; i++ {
		entry := randomEntry()
		_, _, err := tree.Insert(uint64(i), entry.Index, entry.Commitment, false)
		if err != nil {
			b.Fatal(err)
		}
	}
	entries := make([]Entry, batchSize*b.N)
	for i := range entries {
		entries[i] = randomEntry()
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		start := batchSize * i
		end := batchSize * (i + 1)
		_, _, err := tree.BatchInsert(100+uint64(start), entries[start:end], false)
		if err != nil {
			b.Fatal(err)
		}
	}
}
