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
1. Support dPoE and delegator rewards/slashing

## Contract-Controlled Validators

This involves a separate Go module `x/validator` that gives super powers to one specified CosmWasm
contract. We can use Custom Message and Queries between CosmWasm and the chain to enable this.

The `x/validator` module state is more or less:

```go
type Permissions struct {
    // This account can set any of the addresses in this state
    Admin       sdk.AccAddress
    // Address of a CosmWasm contract (CW7) that can set the validator power
    Authority   sdk.AccAddress
    // Address of a CosmWasm contract (CW8) that receives rewards and can distribute them
    // Added in "Distributing Rewards" (if nil, no rewards distributed)
    Distribution sdk.AccAddress
    // Address of a CosmWasm contract (CW9) that receives slashing evidence and can punish validators
    // Added in "Slashing Feedback" (if nil, no slashing occurs)
    Slashing sdk.AccAddress
}

type Validator struct {
    TendermintPubKey    ed25519.PubKey
    Weight              uint64
}
```

The Admin address can set a new contract address or set a new admin address (or clear admin). This is mainly used for bootstrapping, but the admin can remain with some governance vote, to allow swapping out the staking mechanism later.

When the Contract address is changed, the `x/validator` module will make a query to that Contract to get the current
validator set `[]Validator`. Afterwards, it will process `MsgValidatorDiff` to update/patch the validator set, which must
be authorized by `Authority` address to be accepted. We will define a CW-7 spec to define the interface of the contract that
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

Note: The cw7 contract must be highly trusted and should only be set by a governance process with similar security to
the validator set itself, as a buggy/malicious contract can halt or take over the chain.

## Bootstrapping

In the ideal world, we would be able to set up all this in the genesis file. However, the current wasm genesis format
is designed primarily for recovering state dumps made from a previous chain, and not setting up a set of init/execute
messages. Furthermore, it is hard to define all of those ahead of time, as you will need to predict the proper addresses
created in init to refer to later. A more flexible format is something to consider for the future.

For now, bootstrapping will involve a trusted actor setting up the chain properly in the first eg. 10 blocks using a
prepared script everyone agrees on. Here is an example, assuming the trusted Admin is "John":

* Init `x/validator` with Admin=John, Authority=nil, and an InitialValidator of one node
* Upload group and multisig code (store code ids)
* Init CW4/CW7-group contract with all pubkeys of "genesis" validators and proper group weights, Admin=John
* Create both CW3-voting contracts pointing to the CW4/7-group contract (with different thresholds)
* Set CW4/7-group admin to the voting contract #1 (eg. 60%)
* Set `x/validator` Authority to the CW4/7-group contract (properly setting the validator set)
* Set `x/validator` Admin to the voting contract #2 (eg. 80%)

At this point, John no longer has any special access and all of the components are properly wired up together.

My first step would to write such logic off-chain with CosmJS. We can then look how to include such logic
on-chain. We could do this with [some init callbacks](https://github.com/CosmWasm/cosmwasm/issues/467),
and uploading a smart contract with all this init logic as part of genesis. We could also do it with
genesis-only Go code that parses genesis data (eg. pubkeys and voting weights) and runs this series of events.

## Simple PoS Contract

Once we have developed a PoA system using CosmWasm and demonstrated it working and properly updating the validators
on a testnet, we can develop a simple PoS example (and swap them out live). The first PoS example only includes
self-stake and doesn't have rewards or slashing, but let's show how this could work.

Fundamentally, this will be quite similar to the PoA model above, with one change - the contract that updates
the group. We will have:

* CW4/7 group to hold current validator set in CosmWasm (as above)
* Voting contract using this group that can serve as admin for `x/validator`
* Possibly second voting contract for other governance (as needed)
* NEW: token staking contract that is group admin and sets the member weights

The staking contract must define a "staking token" (native or cw20) upon init, as well as an "unbonding period".
It will have 3 main functionalities:

* `SelfStake`: This locks the "staking token" sent with the message. It then adds the respective weight to the group contract.
* `UnStake`: This reduces the sender's self-stake and creates an "undelegating token claim" with the proper expiration. It then updates the group by reducing the sender's weight.
* `Release`: This checks all expired "undelegating token claims" by this validator and sends the appropriate tokens back to their wallet.

## Distributing Rewards

This requires an enhancement to the `x/validator` native module and a new CW8 reward distribution spec.
We need to be able to mint block rewards
in a native token, as well as distribute the FeeCollector tokens, which cannot be done with a generic CosmWasm contract
(for obvious security reasons).

To limit overhead, we define an `Epoch` in the `x/validator` state, which is a delta (of block timestamp) at which rewards are distributed, as well as an block reward rate (per epoch). This is triggered by a `BeginBlock` handler of `x/validator`,
which only runs once per epoch (first block that enters the next epoch) - among other things, this allows some level of "no empty blocks" to work, as we only change state once per epoch (not every block), allowing us to support reasonable "no_empty_blocks" timeouts up to the epoch size. I would recommend epochs on the scale of 5 minutes to 2 hours, depending on the dynamism of the chain (more dynamic => shorter) and the size of the validator set (larger => longer).

When the epoch is completed, the `x/validator` module sends all relevant tokens (both minter block rewards and collected fees)
as `sent_funds` in a `cw8::Distribute` message sent to a `Distibution` contract (added to the `x/validate` state). This
`Distribution` address may be the same as the `Contract` address or may be a different contract. For better composition, it
is recommended to separate this from the group/`Authority` contract.

Note: As with the cw7 contract, this must be highly trusted, as it both maintains funds and is called in
`BeginBlocker` without any gas limit. It cannot take over the chain, but can both halt it (via infinite loop),
as well as steal considerable funds.

## Slashing Feedback

We will not maintain jailing/punishment for downtime on the chain. This is a huge computation overhead and adds questionable value to the chain. Downtime can be handled off-chain in PoA by voting out/down anyone who goes down to long. In PoS by undelegating stake from the validator, and in PoE both by voting to slash the engagement rewards (like PoA) as well as undelegating. We will defer such uptime metrics to off-chain watchdogs, and the worst case here is a liveness challenge (which can happen even with in-protocol jailing - 34% down halts the chain and you cannot even jail those validators as the chain needs to make blocks to do so). In my opinion, the proposer rewards and pre-commit inclusion incentives have negligible benefit in any functioning chain and create new attack vectors in highly Byzantine environments, so we aim for simplicity.

However, we *will* add in-protocol support for double-signing punishments, as this is essential to the security of the chain (consistency guarantees). These must be detected by the `x/validators` module. To do so, we will add a check similar to
[`x/evidence` BeginBlocker](https://github.com/cosmos/cosmos-sdk/blob/master/x/evidence/abci.go), except rather than
[bind the processing to the `slashingKeeper`](https://github.com/cosmos/cosmos-sdk/blob/master/x/evidence/keeper/infraction.go), we will inform a CosmWasm module of the slashing event, and allow it to handle this as needed.

**TODO**: Define callback spec cw9, show example with PoA integration, with PoS integration.

Note: As with the cw7 contract, this must be highly trusted, as it is called in `BeginBlocker` without any gas limit.
If you allow the code to update the `Authority` set, it also provides an attack vector to the validator set. cw7, cw8,
and cw9 contracts should be audited and approved by governance. Just as the `staking`, `slashing`, `distribution` and
`evidence` native modules in the Cosmos-SDK.

### Composition

Here is a diagram of a possible contract setup for a PoS system with slashing and rewards enabled:

```text
   (Admin)                (Authority)              (Distribution)
+--------------+ read   +--------------+   read   +-------------------+
+ Cw3 80% vote + -----> | Cw4/7 Group  | <------  + Reward per weight |
+--------------+        +--------------+          +-------------------+
                             ^
                             | r/w
                          (Slashing)
                       +---------------------+
                       | Staking Module      |
                       |  (plus cw9 support) |
                       +---------------------+
```


Here is a diagram of a possible contract setup for a PoA system with slashing and rewards enabled.
Note we can handle the slashing either directly in the `Authority` group (as shown),
or in the owner of that group (the cw3 60% vote), as both can update the group status.
Pick the one which is easier to extend.

```text
   (Admin)                (Authority+Slashing?)        (Distribution)
+--------------+ read   +----------------+   read   +-------------------+
+ Cw3 80% vote + -----> | Cw4/7 Group    | <------  + Reward per weight |
+--------------+        +----------------+          +-------------------+
                             ^
                             | r/w
                          (Slashing?)
                       +---------------------+
                       | Cw3 60% vote        |
                       +---------------------+
```

## PoE as Simple Mixer

Given the above models, the simplest way to implement PoE is just to create a "mixer" contract.
We can extend the CW4 spec to enable "listeners". That is special contracts that get an update
message each time the group changes. This works similar to the cw7 extension, but rather than make a
special `CustomMsg` call to a native module on update, it would call a wasm contract with a
predefined `ReceiverMsg` (the listener is sensitive and must be set by admin, as a buggy listener
could block all group updates). Also, we only handle `sdk.AccAddress` / `HumanAddr` here, not the
tendermint pubkey, so we are compatible with the generic cw4 groups used by multisigs.

The PoE mixer is simply applies the curve `f(S, E)` to the two input groups to set an output
group. On init, it can query both `PoS` and `PoA` and set values for every address present on either side,
filtering out zeros, in order to get initial conditions. Afterwards, when it receives an update
message, it can calculate the new value for that validator. On the trigger, it can query the specified
validator address on `PoS` and `PoA` contracts, calculate `vote' = f(S', E')` and add that diff to the
group contract it controls.

A picture is worth a thousand works. Here we should how we can achieve full PoE (minus delegations)
with only one minor additions to what we have already:

```text
   (Admin)                (Authority)                 (Distribution)
+--------------+ read   +----------------+   read   +-------------------+
+ Cw3 80% vote + -----> | Cw4/7 Group    | <------  + Reward per weight |
+--------------+        +----------------+          +-------------------+
                             ^
                             | write
                       +---------------------+
                       | PoE mixer           |
                       +---------------------+
                        ^                  ^
             listener  /                    \ listener
            +-------------+               +-------------+
            | Cw4 Group   |               | Cw4 Group   |
            +-------------+               +-------------+
                 ^                               ^
                 | r/w                           | r/w
             (Slashing)                          |
         +---------------------+         +---------------------+
         | Staking Module      |         | Cw3 60% vote        |
         |  (plus cw9 support) |         +---------------------+
         +---------------------+
```

If we want to slash both Engagement and Stake on double-sign, we would need a second contract to call out
to both sides and some more customization. This is doable, but one more step to add.

Note that as we are adding more and more complexity to the contract composition, simple unit tests of
contracts in isolation no longer suffice and we will have to build up much more sophisticated test harnesses
capable of simulating the entire system in unit tests and supporting the full array of native rust tooling
(fuzzing, profiling, backtraces, step-by-step debugging) in composition. In fact, this is the major work
required to extend the PoA and PoS designs into PoE - properly simulating and testing it.

## Governance

Once we have built up such systems. we have a very nice and flexible control over the algorithmic selection
of the validator set, the reward distribution, and how to handle slashing. We show how we can add novel
validator selection algorithms or even combine multiple algorithms easily, such as the PoE mixer above.

However, so far there are two key elements of Cosmos native bPoS system we have not reproduced: delegations
(next section), and governance votes. On-chain governance is essential in most Cosmos SDK applications
to perform numerous adjustments live. Changing parameters of modules, triggering upgrades (via `x/upgrade`),
or even using the permissioning system inside `x/wasm` itself. All of these module expose Proposal types and
Handlers that can be used by the `x/governance` module to perform privileged operations.

We can handle such votes inside CosmWasm with our multisigs, and we even rely on the `Admin` voting contract
to trigger SDK native actions, via proposals that handle `CosmosMsg::Custom(CW7)`. However, they can only
reflect custom messages that were compiled into the wasm build, not arbitrary interfaces registered in Go. We
need a Go module to register all these interfaces and execute them when voting passes. We have two choices to
make here:

* Handle the voting rules in a CosmWasm contract (like Admin) and just reflect some
`CosmosMsg::Custom(Governance::Pass{proposal_id})` message when the vote passes (storing the original sdk interface
mapped by proposal_id in the go module)
* Handle all voting in Go, similar to the current governance contract (using the same Msg types and queries for
maximum compatibility with block explorers), and just calling into the CosmWasm contract once when the proposal is
created to get the proper voting set to use.

Both are possible and we should consider efficiency, code reuse on the blockchain, and client-side compatibility
when making this decision. Currently, I am leaning towards option 2 and forking `x/governance` as the base,
but we will see how all the code bases develop by the time we get here.

## dPoS with Delegators

**TODO**

## dPoE with Delegators

**TODO**
