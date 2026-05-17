"""Unit tests for consensus engine."""
import unittest

from camtc.core.transaction import Transaction, TransactionMeta, Domain
from camtc.core.block import Block
from camtc.core.mempool import TieredMempool
from camtc.consensus.pbft import PBFTEngine, TieredConsensus
from camtc.consensus.reputation import ReputationManager, ValidatorReputation
from camtc.consensus.vrf_election import VRFLeaderElection


class TestMempool(unittest.TestCase):
    def test_enqueue_dequeue(self):
        mp = TieredMempool(tier1_batch=3, tier1_wait_ms=0)
        for i in range(3):
            tx = Transaction(meta=TransactionMeta(
                domain=Domain.HEALTHCARE, semantic_type="cardiac-alert",
                urgency=0.9, economic_value=0.5, submitter_reputation=0.7,
                latency_sensitivity=0.9, regulatory_class=0.8,
            ), tier=1, priority_score=0.95)
            mp.enqueue(tx)
        self.assertEqual(mp.queue_depth(1), 3)
        batch = mp.dequeue_batch(1)
        self.assertEqual(len(batch), 3)
        self.assertEqual(mp.queue_depth(1), 0)


class TestReputation(unittest.TestCase):
    def test_vscore(self):
        rep = ValidatorReputation()
        score = rep.vscore
        self.assertAlmostEqual(score, 1.0, places=1)

    def test_degradation(self):
        rep = ValidatorReputation()
        rep.record_invalid_proposal()
        self.assertLess(rep.vscore, 1.0)
        self.assertTrue(rep.is_tier1_eligible())

    def test_quarantine(self):
        rep = ValidatorReputation(rep=0.1, up=0.1, lat=0.1)
        self.assertTrue(rep.is_quarantined())


class TestPBFT(unittest.TestCase):
    def test_fast_path(self):
        engine = PBFTEngine(
            tier=1, committee=[0, 1, 2, 3],
            quorum_fraction=0.90, max_batch=5, timeout_ms=500,
            enable_fast_path=True,
        )
        block = Block(height=0, epoch=1, tier=1, transactions=[])
        engine.start_proposal(block, 0)

        # Simulate unanimous prepare
        for cid in [1, 2, 3]:
            msg = type('Msg', (), {
                'epoch': 1, 'tier': 1, 'sender_id': cid,
                'block_hash': block.hash(), 'block': block,
            })()
            engine.receive_prepare(msg)

        # After fast-path commit, phase returns to IDLE and block is in committed_blocks
        self.assertEqual(len(engine.committed_blocks), 1)


class TestVRF(unittest.TestCase):
    def test_election(self):
        from camtc.crypto.signatures import generate_keypair, vk_to_bytes
        election = VRFLeaderElection(n_validators=5)
        sk_map = {}
        vk_map = {}
        for i in range(5):
            sk, vk = generate_keypair(seed=i.to_bytes(32, "big"))
            sk_map[i] = bytes(sk)
            vk_map[i] = vk_to_bytes(vk)

        vscores = {i: 0.5 for i in range(5)}
        result = election.elect(sk_map, vk_map, b"\x00" * 32, 1, 1, vscores)
        self.assertIsNotNone(result)
        self.assertIn(result[0], range(5))


if __name__ == "__main__":
    unittest.main()
