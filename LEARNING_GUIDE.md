# CAMTC -- End-to-End Learning Guide

## Read This First

This guide is written so that someone with **basic programming knowledge** can
understand every concept in the CAMTC thesis and codebase from the ground up.
Each section builds on the previous one. Do not skip ahead.

Estimated total learning time: **25-35 hours** depending on your background.

---

## ROADMAP -- The 12 Things You Need to Learn

```
 1. What is a Blockchain? (and why normal blockchains are too slow for hospitals)
 2. Byzantine Fault Tolerance (why nodes can't trust each other)
 3. The PBFT Protocol (how nodes agree without a central authority)
 4. The Problem CAMTC Solves (one-size-fits-all consensus is broken)
 5. How Priority Scoring Works (deciding which transactions are urgent)
 6. Deep Neural Networks (the PriorityNet DNN that replaces manual formulas)
 7. Reinforcement Learning (the PPO agent that adapts thresholds in real-time)
 8. VRF and Leader Election (choosing a leader nobody can predict)
 9. Reputation Systems (the V-Score model that tracks validator trust)
10. Cross-Chain Anchoring (linking to Ethereum for public auditability)
11. How Everything Connects (the full system architecture)
12. Understanding the Code (mapping paper concepts to Python files)
```

---

## PHASE 1: FOUNDATIONS (6-8 hours)

### 1. What is a Blockchain?

**What you need to understand:**

A blockchain is a **linked list of blocks** where each block contains
transactions, and each block's header includes the hash of the previous block.
This "chaining" makes it tamper-evident: change one block, and every subsequent
block's hash changes.

```
Block 0          Block 1          Block 2          Block 3
+--------+      +--------+      +--------+      +--------+
|prev:00 |      |prev:H0 |      |prev:H1 |      |prev:H2 |
|txs: [] | ---> |txs: [] | ---> |txs: [] | ---> |txs: [] |
|hash:H0 |      |hash:H1 |      |hash:H2 |      |hash:H3 |
+--------+      +--------+      +--------+      +--------+
```

**Key terms:**

| Term | Meaning |
|------|---------|
| **Validator** | A computer running the blockchain software. Our system has 10. |
| **Transaction** | A piece of data submitted by a user (e.g., "patient heart rate = 180") |
| **Block** | A group of transactions bundled together |
| **Ledger** | The complete history of all blocks on a node |
| **Hash** | A fixed-size fingerprint of data (SHA-256). Change one bit, hash changes completely |
| **Consensus** | The process by which all validators agree on what blocks to add |
| **Mempool** | A waiting area where transactions sit before being put into blocks |
| **Finality** | The moment a transaction is permanently committed -- it cannot be undone |

**Why this matters for CAMTC:**

In a hospital, a "cardiac alert" transaction and a "monthly audit log" are both
just transactions. But one needs to be committed in **under 500 milliseconds**
and the other can wait **10 seconds**. Traditional blockchains treat them
identically. CAMTC does not.

**Resources to learn more:**
- Article: "What is Blockchain Technology?" by IBM -- https://www.ibm.com/think/topics/blockchain (10 min read)
- Article: "A Gentle Introduction to Blockchain" by Tarun Sukhu, towardsdatascience.com (15 min read)
- Article: "How Does Blockchain Work? Everything You Need to Know" by Simplilearn (20 min read)

---

### 2. Byzantine Fault Tolerance

**The core problem:**

You have 10 computers (validators) that need to agree. Some of them might be
**lying, broken, or malicious** (Byzantine). How do the honest ones still reach
the correct decision?

This is called the **Byzantine Generals Problem**. Imagine 10 generals
surrounding a city. They need to all attack at the same time or all retreat.
But some generals are traitors sending conflicting messages. How do the loyal
generals coordinate?

**The key mathematical result:**

If you have `n` validators and up to `f` can be Byzantine, you need:

```
n >= 3f + 1
```

For our system: n=10, f=3. So we can tolerate up to 3 malicious validators.
If 4 out of 10 go rogue, the system halts (safely -- no wrong blocks are committed).

**Why n >= 3f + 1?**

In the worst case, `f` nodes are silent (offline). The remaining `n - f` nodes
need to make progress. But among those, up to `f` could be Byzantine sending
wrong messages. The honest majority among the responsive nodes is:

```
honest responsive = n - f - f = n - 2f
```

For honest nodes to outvote Byzantine ones:
```
n - 2f > f
n > 3f
n >= 3f + 1
```

**Resources:**
- Original paper: Lamport, Shostak, Pease (1982) "The Byzantine Generals Problem"
- Article: "Byzantine Fault Tolerance -- What It Is and Why It Matters" by Maria Seliner, Binance Academy (10 min read)
- Article: "The Byzantine Generals Problem" explainer by BlockGeeks (12 min read)
- Our code: `consensus/pbft.py` -- the PBFT engine that implements BFT

---

### 3. The PBFT Protocol

**What you need to understand:**

PBFT (Practical Byzantine Fault Tolerance) is a protocol where validators
reach agreement in **3 phases**, even if some are malicious.

```
Phase 1: PRE-PREPARE
  The leader proposes a block.
  Leader sends <PRE-PREPARE, block> to all committee members.

Phase 2: PREPARE
  Each validator checks the block is valid.
  If valid, sends <PREPARE, block_hash> to everyone else.

Phase 3: COMMIT
  Once a validator receives enough PREPARE messages (quorum),
  it sends <COMMIT, block_hash> to everyone.
  Once enough COMMIT messages arrive, the block is committed.
```

**What is a quorum?**

A quorum is the minimum number of agreeing votes needed. The standard BFT
quorum is `2f + 1`. For f=3, that's 7 out of 10.

**Why do we need 3 phases?**

Phase 1 (Pre-Prepare): "Here's what I propose"
Phase 2 (Prepare):    "I checked it, it's valid"
Phase 3 (Commit):     "Enough people checked it, let's finalize"

Each phase adds a layer of certainty. After all 3, even Byzantine nodes
cannot cause two honest nodes to commit different blocks (this is "safety").

**CAMTC's modifications to PBFT:**

1. **Per-tier committees**: Tier-1 uses only 4 nodes (faster), Tier-2 uses 7,
   Tier-3 uses all 10. Smaller committee = faster consensus.

2. **Fast path**: If ALL active Tier-1 validators agree in the Prepare phase
   (unanimous), skip the Commit phase entirely. Saves ~30% of latency.

3. **Quorum fallback**: Tier-1 normally needs 90% quorum (4 of 4). If 2 nodes
   go offline, this is impossible. The system automatically drops to 67%
   quorum (2 of 3). After nodes come back, quorum restores after 3 healthy
   heartbeats.

**Where in the code:** `consensus/pbft.py`
- `start_proposal()` -- Phase 1
- `receive_prepare()` -- Phase 2 (with fast-path check)
- `receive_commit()`  -- Phase 3
- `check_fallback()` / `recover_from_fallback()` -- Fallback mechanism

**Resources:**
- Original paper: Castro & Liskov (1999) "Practical Byzantine Fault Tolerance"
- Article: "What is PBFT? Practical Byzantine Fault Tolerance" by Damian Mingle, Medium (15 min read)
- Article: "PBFT -- Understanding the Consensus Algorithm" by Lisk Academy (10 min read)
- Interactive: Run `python demo.py` and watch DEMO 5 (consensus)

---

### 4. The Problem CAMTC Solves

**Read this carefully -- this is the entire motivation.**

Imagine a hospital blockchain. At 2 AM, a nurse submits a cardiac alert.
At the same millisecond, someone submits a billing record.

In Bitcoin, Ethereum, Hyperledger, or any standard blockchain:

```
Cardiac alert  ----\
                     ----->  [Single Queue]  ----->  [One PBFT Pipeline]
Billing record ----/          (first come,        (all transactions get
                              first served)        the same treatment)
```

The cardiac alert and billing record compete for the same resources. The alert
might wait 2+ seconds. In an ICU, that delay can be dangerous.

**CAMTC's solution:**

```
Cardiac alert  -----> PriorityNet scores it 0.92 -----> Tier 1 (4-node, <500ms)
Medication     -----> PriorityNet scores it 0.72 -----> Tier 2 (7-node, <2s)
Billing record -----> PriorityNet scores it 0.25 -----> Tier 3 (10-node, <10s)
```

Three separate pipelines, each optimized for its urgency class.

**The six research gaps (G1-G6) that CAMTC fills:**

| Gap | Problem | CAMTC Solution |
|-----|---------|---------------|
| G1 | No protocol classifies transactions by urgency | PriorityNet DNN |
| G2 | Single queue causes head-of-line blocking | 3-tier mempool |
| G3 | Leader election ignores reputation | VRF + V-Score |
| G4 | Fixed quorum sizes are inflexible | Adaptive fallback (90% to 67%) |
| G5 | Validators are either trusted or not (binary) | Gradual V-Score degradation |
| G6 | Static scoring formulas can't handle bursts | PPO RL agent adapts thresholds |

**Resources:**
- Our paper: Chapter 1 (Introduction) and Chapter 2 (Problem Definition)
- Compare: Read about Hyperledger Fabric's endorsement policies and notice
  they don't have urgency-based routing

---

## PHASE 2: MACHINE LEARNING (8-10 hours)

### 5. Priority Scoring -- How Transactions Get Ranked

**The core idea:**

Every transaction has metadata. From that metadata, we compute a single
priority score between 0 and 1.

**Input features (6 numbers):**

| Feature | Symbol | What it means | Example (Cardiac Alert) |
|---------|--------|---------------|------------------------|
| Semantic criticality | C | How critical is this type? (lookup table) | 0.95 |
| Urgency | u | How time-critical? (user-submitted) | 0.95 |
| Economic value | v | Financial impact | 0.30 |
| Submitter reputation | r | Trust score of the submitter | 0.80 |
| Latency sensitivity | l | How much does delay hurt? | 0.95 |
| Regulatory exposure | K | Compliance requirements (HIPAA etc.) | 0.90 |

**The old approach (static formula):**

```
P(T) = alpha * C + beta * S + gamma * R + delta * K

where alpha, beta, gamma, delta are hand-picked weights.
```

Problem: These weights are brittle. A mass casualty event floods Tier 1 and
the static formula can't adapt.

**The CAMTC approach (DNN):**

Replace the formula with a neural network that **learns** the right weights
from 100,000 labeled examples.

**Where in the code:**
- Feature extraction: `core/transaction.py` -> `TransactionMeta.to_feature_vector()`
- Criticality lookup: `core/transaction.py` -> `TransactionMeta.criticality`
- Scoring: `ml/priority_net.py` -> `PriorityNet.predict()`

---

### 6. Deep Neural Networks -- PriorityNet

**You need to understand this concept:**

A neural network is a function that takes numbers in and produces numbers out.
It "learns" by seeing thousands of examples and adjusting its internal
parameters (weights) to minimize errors.

**PriorityNet architecture:**

```
Input Layer:        6 neurons  (one per feature)
                    |
Hidden Layer 1:    64 neurons  (ReLU activation)
                    |
Hidden Layer 2:    64 neurons  (ReLU activation)
                    |
Output Layer:       1 neuron   (Sigmoid activation -> outputs 0 to 1)
```

**What each piece does:**

- **Linear transformation:** `output = input * weights + bias`
  This is a weighted sum. The network learns which weights produce good scores.

- **ReLU activation:** `f(x) = max(0, x)`
  This adds non-linearity. Without it, stacking layers would just be one big
  linear function. ReLU lets the network learn complex patterns like
  "if urgency AND regulatory_class are both high, score higher than either alone."

- **Sigmoid activation:** `f(x) = 1 / (1 + e^(-x))`
  Squashes any number into the range (0, 1). Perfect for a priority score.

**Training process:**

```
1. Generate 100,000 synthetic transactions with known correct scores
2. Feed features into the DNN, get a predicted score
3. Compare prediction to correct score (this gap is the "loss")
4. Adjust weights to reduce loss (using "backpropagation")
5. Repeat 200 times (epochs) until loss is tiny
```

**Key metrics:**
- **MSE (Mean Squared Error):** Average of (predicted - actual)^2.
  Our DNN achieves 0.0004. Lower is better.
- **Tier accuracy:** What % of transactions get routed to the correct tier?
  Our DNN achieves 97.6%.

**Why a DNN is better than a formula:**

A linear formula like `P = 0.4*C + 0.3*S + 0.1*R + 0.2*K` can't capture
interactions. For example, a transaction with HIGH urgency AND HIGH regulatory
risk should score even higher than either factor alone would suggest. The DNN's
hidden layers learn these non-linear interactions automatically.

**Where in the code:**
- Data generation: `ml/generate_data.py` -> `generate_dataset()`
- Model definition: `ml/priority_net.py` -> `class PriorityNet`
- Training: `ml/priority_net.py` -> `train_priority_net()`
- Inference: `ml/priority_net.py` -> `PriorityNet.predict()`

**Resources:**
- Article: "Neural Networks -- A Gentle Introduction" by Dr. Andy Thomas, towardsdatascience.com (20 min read)
- Article: "How Neural Networks Work" by IBM -- https://www.ibm.com/think/topics/neural-networks (15 min read)
- Article: "Forward Propagation in Neural Networks" by Simeon Kostadinov, towardsdatascience.com (12 min read)
- Article: "Understanding Activation Functions in Neural Networks" by Avinash Sharma V, Medium (10 min read)
- Interactive: Run `python demo.py` and watch DEMO 2 (DNN training)
- Code: Read `ml/priority_net.py` (only ~50 lines of actual model code)

---

### 7. Reinforcement Learning -- The PPO Agent

**The problem:**

The routing thresholds (0.85 for Tier 1, 0.60 for Tier 2) work well normally.
But during a burst (e.g., a mass casualty event sends 500 cardiac alerts at
once), these thresholds might route too many to Tier 1, overwhelming its
small 4-node committee.

We need the thresholds to **adapt automatically**.

**What is Reinforcement Learning (RL)?**

An agent observes a **state**, takes an **action**, and receives a **reward**.
It learns which actions lead to the highest rewards over time.

```
State:   [Tier1 queue depth, Tier2 queue depth, Tier3 queue depth]
         (normalized to 0-1)

Action:  [adjust threshold1 by +/- 0.05, adjust threshold2 by +/- 0.05]

Reward:  -2.0 if Tier-1 latency exceeds 500ms
         -1.0 if Tier-3 queue overflows
          0.0 otherwise (everything is fine)
```

**Example scenario:**

```
1. State: [0.8, 0.3, 0.1]  (Tier-1 queue is 80% full)
2. Agent action: increase theta1 by 0.03 (from 0.85 to 0.88)
3. Effect: fewer transactions qualify for Tier 1, queue drains
4. Next state: [0.4, 0.5, 0.2]  (Tier-1 relieved)
5. Reward: 0.0 (no penalties -- good!)
```

**What is PPO (Proximal Policy Optimization)?**

PPO is a specific RL algorithm that:
- Learns a "policy" (a mapping from states to actions)
- Makes small, safe updates (proximal = nearby)
- Is stable and doesn't catastrophically forget

The agent is **pre-trained** for 5,000 steps on a simulated workload, then
**fine-tunes online** during live operation.

**Where in the code:**
- Environment: `ml/rl_agent.py` -> `CAMTCRoutingEnv`
- Agent: `ml/rl_agent.py` -> `RLAgent`
- Training: `ml/rl_agent.py` -> `RLAgent.train()`
- Live adaptation: `ml/rl_agent.py` -> `RLAgent.adapt()`

**Resources:**
- Article: "An Introduction to Reinforcement Learning" by Innes Anderson, towardsdatascience.com (15 min read)
- Article: "Reinforcement Learning -- An Introduction" by Sutton and Barto, Chapter 1 (free online book, 20 min read)
- Article: "Proximal Policy Optimization (PPO) Explained" by Jonathan Hui, Medium (15 min read)
- Article: "A Beginner's Guide to Deep Reinforcement Learning" by Pathmind -- https://pathmind.com/wiki/deep-reinforcement-learning (12 min read)
- Original paper: Schulman et al. (2017) "Proximal Policy Optimization Algorithms"
- Try it: Run the dashboard, click "Train PPO Agent", then run a benchmark

---

## PHASE 3: CRYPTOGRAPHY (4-5 hours)

### 8. VRF and Leader Election

**The problem:**

Every epoch (round of consensus), one validator needs to be the **leader** who
proposes the next block. This leader must be chosen so that:

1. **Nobody can predict** who the leader will be (prevents targeted attacks)
2. **Everyone can verify** the selection was fair (no cheating)
3. **Better validators are more likely** to be chosen (reputation matters)

**The solution: VRF (Verifiable Random Function)**

A VRF is like a lottery ticket machine:

```
Input:  private key + seed (previous block hash + epoch number)
Output: a random number + a proof that you computed it correctly
```

**Step by step:**

```
1. At epoch start, each validator computes:
   (hash_v, proof_v) = VRF(my_private_key, hash(prev_block || epoch))

2. Convert hash to a float:  vrf_float = hash_to_float(hash_v)
   (some number between 0 and 1, pseudorandom)

3. Check eligibility:  is vrf_float < Threshold_k(v)?

   Threshold_k(v) = 0.40 * (my_stake / total_stake)
                  + 0.50 * VS(v)           <-- reputation score
                  + 0.10 * (1 - tier_load)  <-- how busy is this tier

   A high-reputation, high-stake validator gets a LARGER threshold,
   making them MORE likely to pass the check.

4. Among all eligible validators, the one with the SMALLEST hash wins.
   ("min-ticket wins" -- like the lowest lottery number)
```

**Why this works:**

- The output is pseudorandom (nobody can predict without the private key)
- The proof lets anyone verify the computation (using the public key)
- Reputation increases your eligibility threshold, but the winner is still
  random among the eligible set -- so it's fair but biased toward reliable nodes

**Where in the code:**
- VRF evaluate/verify: `crypto/vrf.py`
- Election logic: `consensus/vrf_election.py` -> `VRFLeaderElection.elect()`
- Threshold formula: Equation 2 in the paper, `vrf_election.py` line for `compute_threshold_with_vscore()`

**Resources:**
- Paper: Micali et al. (1999) "Verifiable Random Functions"
- Article: "What is a Verifiable Random Function (VRF)?" by Algorand Developers, developer.algorand.org (10 min read)
- Article: "VRF -- Verifiable Random Functions Explained" by Chainlink, chain.link (12 min read)
- Article: "Cryptographic Sortition in Blockchains" by Tarun Chitra, Medium (15 min read)
- Try it: `curl http://localhost:8000/api/proof/vrf?epoch=1` and `?epoch=5`

---

### Ed25519 Signatures

**What it is:**

Every transaction is signed with the sender's private key. Anyone can verify
the signature using the sender's public key.

```
Signing:   signature = Ed25519.sign(private_key, transaction_data)
Verifying: is_valid = Ed25519.verify(public_key, transaction_data, signature)
```

If someone tampers with the transaction data, the signature becomes invalid.

**Why Ed25519 specifically:**
- A single verification takes under 100 microseconds (fast)
- Deterministic (same input = same signature, no random nonce needed)
- Constant-time (resistant to timing side-channel attacks)

**Where in the code:** `crypto/signatures.py`

---

### Merkle Trees

**What it is:**

A Merkle tree is a binary tree of hashes. The **root hash** is a single
fingerprint that represents ALL transactions in a block.

```
                    Merkle Root
                   /           \
              Hash(01)        Hash(23)
              /    \          /    \
          Hash(0) Hash(1) Hash(2) Hash(3)
            |       |       |       |
          tx0     tx1     tx2     tx3
```

**Why it matters:**

To prove that tx2 is in the block, you only need:
- Hash(3) (the sibling)
- Hash(01) (the uncle)

That's 2 hashes instead of all 4. For 1 million transactions, you only need
20 hashes (log2 of 1,000,000). This is called a **Merkle proof**.

**Where in the code:**
- Tree construction: `crypto/merkle.py` -> `merkle_root()`
- Proof generation: `crypto/merkle.py` -> `merkle_proof()`
- Proof verification: `crypto/merkle.py` -> `verify_merkle_proof()`

---

### AES-256-GCM Encryption

**What it is:**

Patient data in transactions is encrypted before being submitted to the
blockchain. Only the hash of the ciphertext goes on-chain.

```
Original data  -->  AES-256-GCM encrypt(key, data)  -->  ciphertext
                                                           |
                                                           v
                                              Only hash(ciphertext) stored on-chain
```

This satisfies HIPAA requirements: sensitive data never appears in the ledger.

**Where in the code:** `crypto/encryption.py`

**Resources for all crypto:**
- Article: "Public Key Cryptography Explained" by SSL2Buy, ssl2buy.com (10 min read)
- Article: "What is Public Key Cryptography?" by Cloudflare, cloudflare.com (8 min read)
- Article: "Merkle Trees -- A Visual Introduction" by Rui Zhi Dong, medium.com (10 min read)
- Article: "What is a Merkle Tree?" by Bitcoinwiki (8 min read)
- Article: "Ed25519 -- High-Speed High-Security Signatures" by Daniel J. Bernstein et al., ed25519.cr.yp.to (technical reference)
- Article: "AES Encryption Explained" by SSL2Buy, ssl2buy.com (8 min read)
- Try it: `curl http://localhost:8000/api/proof/merkle`

---

## PHASE 4: SYSTEM COMPONENTS (4-5 hours)

### 9. V-Score Reputation Model

**The problem:**

How do you know which validators are reliable? You can't just check once --
you need to track their behavior over time.

**V-Score formula:**

```
VS(v) = 0.50 * Rep(v)  +  0.30 * Up(v)  +  0.20 * Lat(v)
```

| Component | What it tracks | Starts at | How it degrades |
|-----------|---------------|-----------|-----------------|
| Rep (Reputation) | Proposal correctness and vote validity | 1.0 | -0.10 per invalid proposal, +0.02 per correct |
| Up (Uptime) | Fraction of time responding to heartbeats | 1.0 | -0.05 per silent epoch |
| Lat (Latency) | Inverse of mean response time | 1.0 | Decreases as response times increase |

**Eligibility thresholds:**

```
VS >= 0.30  ->  Can participate in Tier-1
VS >= 0.15  ->  Can participate in Tier-2 and Tier-3
VS <  0.15  ->  Quarantined (banned until manual review)
```

**Why asymmetric updates?**

Recovery is intentionally slow. An invalid proposal costs -0.10, but a correct
one only earns +0.02. So a validator needs 5 correct proposals to recover from
1 mistake. This prevents validators from gaming the system by alternating
between good and bad behavior.

**Where in the code:** `consensus/reputation.py`

**Try it:** `curl http://localhost:8000/api/proof/reputation`

---

### 10. Ethereum Anchoring

**The problem:**

CAMTC is a **permissioned** blockchain (only authorized validators participate).
External auditors (regulators, insurance companies) can't access the private
network. How can they verify that transactions were processed correctly?

**The solution:**

After each committed block, the system submits the block's Merkle root to a
public **Ethereum** smart contract. This is a one-way bridge:

```
CAMTC Private Ledger                        Ethereum Public Chain
+------------------+                        +------------------+
| Block 42:        |   anchorStateRoot()    | Anchor #42:      |
|   tx: cardiac    |  ------------------->  |   merkleRoot:    |
|   tx: medication |   (async, via Web3)    |     0x4a2b...    |
|   merkle_root:   |                        |   blockHeight: 42|
|     0x4a2b...    |                        |   epoch: 15      |
+------------------+                        +------------------+
```

**How verification works:**

```
1. Auditor asks: "Was this cardiac alert really committed?"
2. Auditor checks Ethereum for the Merkle root
3. Auditor requests a Merkle proof from a CAMTC node
4. Auditor verifies: proof matches root on Ethereum
5. Done -- verified without ever accessing the private network
```

**The Solidity contract:**

```solidity
function anchorStateRoot(
    bytes32 _merkleRoot,     // Hash of all tx hashes in the block
    uint256 _blockHeight,    // Which block
    uint256 _epoch,          // Which epoch
    bytes32 _commitCertHash  // Proof that PBFT consensus completed
) external onlyOwner returns (uint256)
```

**Where in the code:**
- Smart contract: `anchor/contract.sol`
- Anchor logic: `anchor/ethereum_anchor.py`
- In simulator: `simulator.py` (anchors after Tier-1 and Tier-3 commits)

**Resources:**
- Article: "What are Smart Contracts? A Beginner's Guide" by Consensys, consensys.io (10 min read)
- Article: "Ethereum Smart Contracts -- A Guide for Developers" by Ethereum.org, ethereum.org (15 min read)
- Article: "What is a Merkle Proof?" by Mycelium, mycelium.com (8 min read)

---

## PHASE 5: PUTTING IT ALL TOGETHER (3-4 hours)

### 11. Full System Architecture

**The complete flow from start to finish:**

```
                              CAMTC SYSTEM
 ============================================================================
                                                                           
  CLIENT                                                                     EXTERNAL
    |                                                                         AUDITOR
    | 1. Submit transaction                                                    |
    |    (signed with Ed25519)                                                 |
    v                                                                         |
  +------------------+                                                        |
  |    GATEWAY       |                                                        |
  |  (FastAPI)       |                                                        |
  |  - Verify sig    |                                                        |
  |  - Parse metadata|                                                        |
  +--------+---------+                                                        |
           |                                                                 |
           | 2. Forward to PriorityNet                                        |
           v                                                                 |
  +------------------+                                                        |
  |  PRIORITYNET DNN |                                                        |
  |  Input: [C,u,v,r,l,K]                                                    |
  |  Output: P(T) in [0,1]                                                   |
  +--------+---------+                                                        |
           |                                                                 |
           | 3. RL Agent adjusts thresholds                                   |
           v                                                                 |
  +------------------+                                                        |
  |  TIER ROUTING    |                                                        |
  |  P > 0.85 -> T1  |  Emergency                                            |
  |  P > 0.60 -> T2  |  Urgent                                               |
  |  P <= 0.60 -> T3 |  Routine                                              |
  +--------+---------+                                                        |
           |                                                                 |
           | 4. Enqueue in tier-specific queue                                |
           v                                                                 |
  +------------------+                                                        |
  |  TIERED MEMPOOL  |                                                        |
  |  Q1 | Q2 | Q3   |                                                        |
  |  (5) | (20)| (50) |  <-- max batch sizes                                 |
  +--------+---------+                                                        |
           |                                                                 |
           | 5. Batch ready -> elect leader                                   |
           v                                                                 |
  +------------------+      +------------------+                              |
  | VRF ELECTION     |----->| V-Score Lookup   |                              |
  | min-ticket wins  |      | weights:         |                              |
  | weighted by      |      | 40% stake        |                              |
  | stake + VS + load|      | 50% reputation   |                              |
  +--------+---------+      | 10% tier load    |                              |
           |                +------------------+                              |
           | 6. Leader proposes block                                         |
           v                                                                 |
  +------------------+                                                        |
  |  PBFT CONSENSUS  |                                                        |
  |  Per-tier engine |                                                        |
  |  Phase 1: Pre-Pre|  -> leader sends block                                |
  |  Phase 2: Prepare|  -> all vote (fast path if unanimous)                 |
  |  Phase 3: Commit |  -> quorum reached, block finalized                   |
  |                  |                                                        |
  |  T1: 4 nodes, 90% quorum, fallback to 67%                               |
  |  T2: 7 nodes, 67% quorum                                                |
  |  T3: 10 nodes, 67% quorum                                               |
  +--------+---------+                                                        |
           |                                                                 |
           | 7. Block committed                                               |
           v                                                                 |
  +------------------+      +------------------+        +------------------+
  |     LEDGER       |      | V-SCORE UPDATE   |        | ETHEREUM ANCHOR  |
  | (all 10 nodes    |      | leader: +0.02    |        | state root ->    |---> Auditor
  |  get the same    |      | invalid: -0.10   |        | smart contract   |    verifies
  |  block)          |      | silent: -0.05    |        | (async)          |
  +------------------+      +------------------+        +------------------+
```

---

### 12. Mapping Paper Concepts to Code Files

| Paper Concept | Paper Section | Code File | Key Class/Function |
|---------------|---------------|-----------|-------------------|
| Priority Score (Def 1) | Problem Def 2.1 | `core/transaction.py` | `TransactionMeta.to_feature_vector()` |
| Tier Routing Policy | Problem Def 2.2 | `core/mempool.py` | `TieredMempool.enqueue()` |
| Threat Model | Problem Def 2.3 | `consensus/pbft.py` | Byzantine handling in vote loops |
| PriorityNet DNN | Proposed 3.3 | `ml/priority_net.py` | `class PriorityNet(nn.Module)` |
| PPO RL Agent | Proposed 3.4 | `ml/rl_agent.py` | `class RLAgent`, `CAMTCRoutingEnv` |
| Adaptive PBFT | Proposed 3.6 | `consensus/pbft.py` | `class PBFTEngine` |
| VRF Election | Proposed 3.7 | `consensus/vrf_election.py` | `VRFLeaderElection.elect()` |
| V-Score | Proposed 3.8 | `consensus/reputation.py` | `class ValidatorReputation` |
| Fallback Mechanism | Proposed 3.5 | `consensus/pbft.py` | `check_fallback()`, `recover_from_fallback()` |
| Ethereum Anchor | Proposed 3.9 | `anchor/ethereum_anchor.py` | `EthereumAnchorSimulator.anchor_block()` |
| Transaction Lifecycle (Alg 1) | Proposed 3.10 | `simulator.py` | `submit_transaction()` |
| Consensus Flow (Alg 2) | Proposed 3.10 | `simulator.py` | `_run_consensus()` |
| Safety Theorem | Proposed 3.11 | (formal proof in paper) | Quorum intersection guaranteed by `quorum_size` |
| Liveness Theorem | Proposed 3.11 | (formal proof in paper) | Fallback ensures `2f+1` can always commit |
| Message Complexity | Proposed 3.11 | `benchmarks/baselines/` | `PBFTBaseline`, `HotStuffBaseline` |
| PriorityNet Training | Requirements 5.6 | `ml/generate_data.py` | `generate_dataset()` |
| Tier Parameters | Requirements 5.5 | `config/settings.py` | `TierConfig` dataclass |
| Workload Generator | Testing 5.1 | `benchmarks/workload.py` | `WorkloadGenerator` |
| 10-node Testbed | Testing 5.1 | `network/node.py` | `class ValidatorNode` |
| Baseline Protocols | Testing 5.1 | `benchmarks/baselines/protocols.py` | All three baselines |
| Byzantine Injection | Testing 5.6 | `simulator.py` | `inject_byzantine()` |
| Fallback Evaluation | Testing 5.7 | `simulator.py` | `trigger_fallback()` |

---

## PHASE 6: RUNNING AND EXPLORING (2-3 hours)

### Hands-On Exercises

**Exercise 1: Watch the DNN train**
```bash
python demo.py
# Watch DEMO 2: see the loss curve drop from 0.005 to 0.0004
# Notice how the bar chart fills up as loss decreases
```

**Exercise 2: Submit different transactions and see routing change**
```bash
python -m camtc.main --train &
# Wait for training to complete, then:

# High urgency -> Tier 1
curl -X POST http://localhost:8000/api/transaction \
  -H "Content-Type: application/json" \
  -d '{"domain":"healthcare","semantic_type":"cardiac-alert","urgency":0.95}'
# Response: {"priority_score": 0.8987, "tier": 1}

# Low urgency -> Tier 3
curl -X POST http://localhost:8000/api/transaction \
  -H "Content-Type: application/json" \
  -d '{"domain":"healthcare","semantic_type":"audit-log","urgency":0.05}'
# Response: {"priority_score": 0.2599, "tier": 3}
```

**Exercise 3: See VRF election change per epoch**
```bash
curl http://localhost:8000/api/proof/vrf?epoch=1
curl http://localhost:8000/api/proof/vrf?epoch=5
curl http://localhost:8000/api/proof/vrf?epoch=10
# Each gives a different winner
```

**Exercise 4: Inject Byzantine faults**
```bash
curl -X POST "http://localhost:8000/api/simulate/byzantine?n_faulty=3"
curl -X POST "http://localhost:8000/api/benchmark/start?n_transactions=1000"
curl http://localhost:8000/api/metrics
# System still works with 3 faulty validators
```

**Exercise 5: Trigger quorum fallback**
```bash
curl -X POST "http://localhost:8000/api/simulate/fallback?n_offline=2"
curl http://localhost:8000/api/consensus
# See fallback_active: true, quorum drops from 90% to 67%
```

**Exercise 6: Open the dashboard**
```bash
python -m camtc.main --train
# Open http://localhost:8080 in browser
# Click "Run 10K Transactions"
# Watch the dashboard update in real-time
```

---

## APPENDIX: Key Equations Reference

**Priority Score (Equation 1):**
```
P(T) = alpha * C(T) + beta * S(T) + gamma * R(T) + delta * K(T)
```

**V-Score (Equation 2):**
```
VS(v) = 0.50 * Rep(v) + 0.30 * Up(v) + 0.20 * Lat(v)
```

**VRF Eligibility Threshold (Equation 3):**
```
Theta_k(v) = 0.40 * (stake_v / total_stake)
           + 0.50 * VS(v)
           + 0.10 * (1 - load_k)
```

**Quorum Intersection Lemma:**
```
|A intersection B| >= 2q*n - n >= f + 1
(at least one honest validator in any two quorums)
```

**Safety Theorem:**
```
If n >= 3f+1 and quorum >= 2f+1, no two honest validators commit conflicting blocks.
```

**Liveness Theorem:**
```
After GST, if >= 2f+1 validators are honest and responsive, every transaction commits.
```

**Message Complexity:**
```
Per tier: O(|C_k|^2) where C_k is the committee size
Tier-1: O((n/3)^2) = O(n^2/9)  -- 9x cheaper than full PBFT
```

---

## APPENDIX: Reading Order for the Thesis

```
1. Abstract           (1 page -- high-level overview)
2. Chapter 1          (3 pages -- motivation, problem, solution summary)
3. Chapter 3          (8 pages -- the full proposed system)
   Then understand the components:
4. Section 3.3        (DNN Priority Scoring)
5. Section 3.4        (RL Adaptation)
6. Section 3.6        (PBFT Protocol)
7. Section 3.7        (VRF Election)
8. Section 3.8        (V-Score)
9. Section 3.5        (Fallback Mechanism)
10. Section 3.9       (Ethereum Anchoring)
11. Section 3.11      (Formal Proofs)
    Then the evaluation:
12. Chapter 4         (Testing and Results)
    Finally:
13. Chapter 2         (Problem Definition -- makes more sense after)
14. Chapter 5         (Related Work -- compares with existing systems)
15. Chapter 6         (Conclusion and Future Work)
```

---

## APPENDIX: External Resources Summary

| Topic | Resource | Type | Time |
|-------|----------|------|------|
| Blockchain basics | IBM: "What is Blockchain Technology?" | Article | 10 min |
| Blockchain deep dive | Tarun Sukhu: "A Gentle Introduction to Blockchain" (towardsdatascience) | Article | 15 min |
| Byzantine Generals | Binance Academy: "Byzantine Fault Tolerance" | Article | 10 min |
| Byzantine Generals (deep) | Lamport, Shostak, Pease (1982) original paper | Paper | 45 min |
| PBFT | Castro & Liskov (1999) original paper | Paper | 45 min |
| PBFT explained | Damian Mingle: "What is PBFT?" (Medium) | Article | 15 min |
| Neural Networks | Dr. Andy Thomas: "Neural Networks -- A Gentle Introduction" (towardsdatascience) | Article | 20 min |
| Neural Networks (deep) | IBM: "How Neural Networks Work" | Article | 15 min |
| Activation Functions | Avinash Sharma V: "Understanding Activation Functions" (Medium) | Article | 10 min |
| Forward Propagation | Simeon Kostadinov: "Forward Propagation in Neural Networks" (towardsdatascience) | Article | 12 min |
| RL Basics | Innes Anderson: "An Introduction to Reinforcement Learning" (towardsdatascience) | Article | 15 min |
| RL (book) | Sutton & Barto: "Reinforcement Learning -- An Introduction" Ch. 1 (free online) | Book chapter | 20 min |
| PPO | Jonathan Hui: "Proximal Policy Optimization (PPO) Explained" (Medium) | Article | 15 min |
| PPO (deep) | Schulman et al. (2017) original paper | Paper | 30 min |
| Deep RL | Pathmind: "A Beginner's Guide to Deep Reinforcement Learning" | Article | 12 min |
| Ed25519 | Bernstein et al.: ed25519.cr.yp.to | Reference | 10 min |
| Public Key Crypto | Cloudflare: "What is Public Key Cryptography?" | Article | 8 min |
| Public Key Crypto (deep) | SSL2Buy: "Public Key Cryptography Explained" | Article | 10 min |
| Merkle Trees | Rui Zhi Dong: "Merkle Trees -- A Visual Introduction" (Medium) | Article | 10 min |
| Merkle Trees (deep) | Bitcoinwiki: "What is a Merkle Tree?" | Article | 8 min |
| VRF | Algorand Developers: "What is a VRF?" (developer.algorand.org) | Article | 10 min |
| VRF (deep) | Chainlink: "VRF -- Verifiable Random Functions Explained" | Article | 12 min |
| VRF (technical) | Tarun Chitra: "Cryptographic Sortition in Blockchains" (Medium) | Article | 15 min |
| Ethereum Contracts | Consensys: "What are Smart Contracts?" | Article | 10 min |
| Ethereum Contracts (deep) | Ethereum.org: "Ethereum Smart Contracts -- A Guide for Developers" | Article | 15 min |
| AES Encryption | SSL2Buy: "AES Encryption Explained" | Article | 8 min |
| PyTorch basics | PyTorch official tutorials (60-minute blitz) | Tutorial | 60 min |
| FastAPI basics | FastAPI official documentation -- First Steps | Web docs | 30 min |
