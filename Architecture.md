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
1. Bootstrapping
1. Implement PoS via token-locking contract
1. Distribute rewards to validators (lazy calculated, per epoch, not every block)
1. Manage Slashing feedback when evidence is submitted, slashing done in contract
1. PoE as mixer between PoA and PoS implementations
1. Governance control and voting power
1. Support dPoS and delegator rewards/slashing
1. Experiment with different curves for PoE (and enable open experimentation)

## Contract-Controlled Validators

This involves a separate Go module `x/validator` that gives super powers to one specified CosmWasm
contract. We can use Custom Message and Queries between CosmWasm and the chain to enable this.

The `x/validator` module state is more or less:

```go
type Permissions struct {
    Admin       sdk.AccAddress
    Contract    sdk.AccAddress
}

type Validator struct {
    TendermintPubKey    ed25519.PubKey
    Weight              uint64
}
```

The Admin address can set a new contract address or set a new admin address (or clear admin). This is mainly used for bootstrapping, but the admin can remain with some governance vote, to allow swapping out the staking mechanism later.

When the Contract address is changed, the `x/validator` module will make a query to that Contract to get the current
validator set `[]Validator`. Afterwards, it will process `MsgValidatorDiff` to update/patch the validator set, which must
be authorized by `Contract` address to be accepted. We will define a CW-7 spec to define the interface of the contract that
can interact with the `x/validator` module.

`x/validator` implements `EndBlocker` and will send Tendermint any diffs to the validator set that occurred in this block.

## Simple PoA Contract

We have built out the [CW3 multisig spec](https://github.com/CosmWasm/cosmwasm-plus/blob/master/packages/cw3/README.md)
and are working to [separate groups from the voting conditions](https://github.com/CosmWasm/cosmwasm-plus/issues/80).
Groups will be defined in CW4.

We can start with a standard, flexible multisig design. The group that stores the voters will implement not only
CW4, but also CW7 and can be registered on `x/validator`. (Note that CW7 requires the Validator pubkey in addition
to an sdk.AccAddress, so we will have a separate endpoint for people to pre-register a pubkey for their sdk.AccAddress
on the CW7 group contract, which will be used when they are given voting weight).

There are 2 voting contracts. Contract A, with eg. 60% approval will allow updating the group. As the group
implements CW7, this will automatically update the validator set upon changes. Contract B with eg. 80% approval
can be the Admin and that can be used to swap out to another consensus module.

## Bootstrapping

In the ideal world, we would be able to set up all this in the genesis file. However, the current wasm genesis format
is designed primarily for recovering state dumps made from a previous chain, and not setting up a set of init/execute
messages. Furthermore, it is hard to define all of those ahead of time, as you will need to predict the proper addresses
created in init to refer to later. A more flexible format is something to consider for the future.

For now, bootstrapping will involve a trusted actor setting up the chain properly in the first eg. 10 blocks using a
prepared script everyone agrees on. Here is an example, assuming the trusted Admin is "John":

* Init `x/validator` with Admin=John, Contract=nil, and an InitialValidator of one node
* Upload group and multisig code (store code ids)
* Init CW4/CW7-group contract with all pubkeys of "genesis" validators and proper group weights, Admin=John
* Create both CW3-voting contracts pointing to the CW4/7-group contract (with different thresholds)
* Set CW4/7-group admin to the voting contract #1 (eg. 60%)
* Set `x/validator` contract to the CW4/7-group contract (properly setting the validator set)
* Set `x/validator` admin to the voting contract #2 (eg. 80%)

At this point, John no longer has any special access and all of the components are properly wired up together.

My first step would to write such logic off-chain with CosmJS. We can then look how to include such logic
on-chain. We could do this with [some init callbacks](https://github.com/CosmWasm/cosmwasm/issues/467),
and uploading a smart contract with all this init logic as part of genesis. We could also do it with
genesis-only Go code that parses genesis data (eg. pubkeys and voting weights) and runs this series of events.

## Simple PoS Contract

Once we have developed a PoA system using CosmWasm and demonstrated it working and properly updating the validators
on a testnet, we can develop a simple PoS example (and swap them out live). The first PoS example only includes
self-stake and doesn't have rewards or slashing, but let's show how this could work.

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
