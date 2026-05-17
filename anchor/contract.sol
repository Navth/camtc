// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * CAMTC State Anchor Contract
 *
 * Anchors permissioned ledger state roots to Ethereum for public auditability.
 * Each anchor stores: Merkle root, block height, epoch number, and commit cert hash.
 */
contract CAMTCAnchor {
    struct AnchorEntry {
        bytes32 merkleRoot;
        uint256 blockHeight;
        uint256 epoch;
        bytes32 commitCertHash;
        uint256 timestamp;
        address anchorer;
    }

    mapping(uint256 => AnchorEntry) public anchors;
    uint256 public anchorCount;

    event StateAnchored(
        uint256 indexed index,
        bytes32 merkleRoot,
        uint256 blockHeight,
        uint256 epoch,
        bytes32 commitCertHash
    );

    address public owner;

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorized");
        _;
    }

    function anchorStateRoot(
        bytes32 _merkleRoot,
        uint256 _blockHeight,
        uint256 _epoch,
        bytes32 _commitCertHash
    ) external onlyOwner returns (uint256) {
        uint256 index = anchorCount;
        anchors[index] = AnchorEntry({
            merkleRoot: _merkleRoot,
            blockHeight: _blockHeight,
            epoch: _epoch,
            commitCertHash: _commitCertHash,
            timestamp: block.timestamp,
            anchorer: msg.sender
        });
        anchorCount++;

        emit StateAnchored(index, _merkleRoot, _blockHeight, _epoch, _commitCertHash);
        return index;
    }

    function verifyAnchor(
        uint256 _index,
        bytes32 _merkleRoot
    ) external view returns (bool) {
        if (_index >= anchorCount) return false;
        return anchors[_index].merkleRoot == _merkleRoot;
    }

    function getAnchor(uint256 _index) external view returns (
        bytes32 merkleRoot,
        uint256 blockHeight,
        uint256 epoch,
        bytes32 commitCertHash,
        uint256 timestamp,
        address anchorer
    ) {
        require(_index < anchorCount, "Index out of bounds");
        AnchorEntry storage entry = anchors[_index];
        return (
            entry.merkleRoot,
            entry.blockHeight,
            entry.epoch,
            entry.commitCertHash,
            entry.timestamp,
            entry.anchorer
        );
    }
}
