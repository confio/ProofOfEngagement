# PoE Implementation and Architecture

In this document, we will explore how one could implement PoE for a Cosmos SDK chain,
along with a rough roadmap.

Since PoE is not just one algorithm from game theory, but a solution space
achieved by combining different models into a solution that best fits the
*current state of the chain*, there is a need for both flexibility and evolution
in the implementation. Given this, we propose to construct PoE via multiple CosmWasm
contracts, with clearly defined interfaces and a clean composition model. This allows
us to adjust individual contract, swap out implementations, and even rewire the
composition model as we explore the PoE solution space.

We propose to get to a working foundational PoE implementation with the following
roadmap, where each stage builds on the last:

1. Controlling validator set with a privileged contract
1. Implement PoA via modified multisig contracts (no rewards)
1. Implement PoS via token-locking contract
1. Distribute rewards to validators (lazy calculated, per epoch, not every block)
1. Manage Slashing feedback when evidence is submitted, slashing done in contract
1. PoE as mixer between PoA and PoS implementations
1. Governance control and voting power
1. Support dPoS and delegator rewards/slashing
1. Experiment with different curves for PoE (and enable open experimentation)

## Contract-Controlled Validators

**TODO**

## Simple PoA Contract

**TODO**

## Simple PoS Contract

**TODO**

## Distributing Rewards

**TODO**

## Slashing Feedback

**TODO**

## PoE as Simple Mixer

**TODO**

## Governance

**TODO**

## dPoS with Delegators

**TODO**

## PoE Experiments

**TODO**
