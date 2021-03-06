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
CW4, but also CW7 and can be registered on `x/validator`. Note that CW7 requires the Tendermint PubKey in addition
to an sdk.AccAddress, in order to provide the validator set updates to `x/validator`. Thus, we will have a separate
HandleMsg variant on the CW7 contract for people to pre-register a pubkey for their sdk.AccAddress
on the CW7 group contract. This is permissionless to provide a mapping for the message sender,
but will have no impact on the voting set the address is assigned a voting weight.

There are 2 voting contracts. Contract A, with eg. 60% approval will allow updating the group. As the group
implements CW7, this will automatically update the validator set upon changes. This means the tendermint consensus layer
is just a mirror of the multisig voters. And these voters (who are also the validators) can vote to add voters/validators
to the multisig + validator set (or remove them).

This is a minimal PoA setup as used in many chains. In addition, we can add a Contract B with eg. 80% approval
can be the `Admin` in `x/validator`. This allows a supermajority of the validator set to change the consensus algorithm
(more precisely the *validator set selection* algorithm, as we always use tendermint BFT... bPoS is often
mis-labeled a consensus algorithm)

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
We need a native module to be able to mint block rewards
in a native token, as well as distribute the FeeCollector tokens. For obvious security reasons,
we cannot allow arbitrary CosmWasm contract to mint block rewards or distribute the collected fees. So we add a
`Distribution` address to `x/validator` to control that permission.

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

CW9 is essentially one message that must be supported from the contact `HandleMsg::Byzantine{type, tm_pubkey}` with
the type (`abci.EvidenceType_DUPLICATE_VOTE`, `abci.EvidenceType_LIGHT_CLIENT_ATTACK`) and the original tendermint
pubkey. The module doing the slashing needs to implement CW7 or be able to query the CW7 module in order to map
the Tendermint PubKey to the SDK Address of the validator (which is the one with staking/voting power).

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
                       | Staking Contract    |
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
         | Staking Contract    |         | Cw3 60% vote        |
         |  (plus cw9 support) |         +---------------------+
         +---------------------+
```

If we want to slash both Engagement and Stake on double-sign, we would need a second contract to call out
to both sides and some more customization. This is doable, but one more step to add.

**Important** As we are adding more and more complexity to the contract composition, simple unit tests of
contracts in isolation no longer suffice and we will have to build up much more sophisticated test harnesses
capable of simulating the entire system. All current multi-component integration tests (contract-contract
and contract-native callbacks) require running compiled wasm contracts inside `wasmd` and do not allow detailed
debugging of the contract internals. In order to make use of the full array of native rust tooling
(fuzzing, profiling, backtraces, step-by-step debugging) to allow us the same confidence in multi-contract
composition as with single contract unit tests, we will need to build a native Rust (no wasm) integration test harness.
In fact, this is the major work required to extend the PoA and PoS designs into PoE - properly simulating and testing it
in order to provide confidence in implementation correctness.

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

Adding delegators to PoS adds complexity on three fronts.

The first is the stake accounting on the Staking Contract, in order to produce the proper voting weights and withdrawls.
This should actually be a relatively minor change, an extra message to stake to a different address, and a bit more
state info, but nothing that cannot be unit tested.

The second complication is on Slashing. As long as we don't allow instant re-delegation, but force a full undelegate
followed by delegate, then the Slashing logic (and slashing unbonding tokens) for delegators is no more complicated
that for self-staking validators. I would consider instant redelegation a feature for v2 of dPoS to get us to a
usable MvP early as possible.

The third complication is Distribution. We can no longer do the naive distribution based on final weight, but need
to take into account who is delegator, who is validator, and what the commission rate is. This makes it impossible
to use a generic voting-weight based distribution module, but rather we must integrate the distribution directly inside
the staking contract. I will present two ways of handling the distribution aspect in the [Composition](#dpos-composition)
section below.

### Staking Integration

We may well want to allow other contracts to interact with our custom dPoS implementation without any changes.
Allowing us to reuse all staking-related contracts eg. Staking Derivatives, which were designed to work with the
standard Cosmos SDK `x/staking` module, to work with our contract-based dPoS system without any changes.

To do so, we need to register a different [`StakingQuerier`](https://github.com/CosmWasm/wasmd/blob/master/x/wasm/internal/keeper/query_plugins.go#L123-L186) and [`StakingEncoder`](https://github.com/CosmWasm/wasmd/blob/master/x/wasm/internal/keeper/handler_plugin.go#L114-L192)
in a custom blockchain app. These would register some contract address via genesis/governance and use that to route
such queries to the specified contract rather than the default staking module.

### dPoS Composition

**Option 1** This is actually a simpler composition that the simpler PoS, at the expense of a more complicated
staking contract, which now handles staking, slashing, and distribution in one monolith.

```text
   (Admin)                (Authority)
+--------------+ read   +--------------+
+ Cw3 80% vote + -----> | Cw4/7 Group  |
+--------------+        +--------------+
                             ^
                             | r/w
                       (Slashing + Distribution)
                       +---------------------+
                       | Staking Contract    |
                       |  (plus cw8 support) |
                       |  (plus cw9 support) |
                       +---------------------+
```

**Option 2** If we wish to reduce monoliths, and allow some more code reuse with dPoE, then we have to define a 2 step distribution methods. We can provide a generic distribution module, which takes a set of funds, and splits it up
based on the voting weights (this is total income -> per validator income), handling rounding and such.
It then transfers those funds to a new contract along with a list of all accounts that should be distributed to.

The staking contract then gets that first split done, and just calculated the validator/delegator split for each validator,
based on commission. I am not sure how much code savings is provided there, but this does allow some code-reuse with
dPoE (but maybe we can just import utility functions to get the same code reuse with less complexity):

```text
   (Admin)                (Authority)             (Distribution)
+--------------+ read   +--------------+       +-----------------+
+ Cw3 80% vote + -----> | Cw4/7 Group  |<----- + Reward splitter +
+--------------+        +--------------+       +-----------------+
                             ^                   /
                             | r/w              / send funds to staking to sub-split
                         (Slashing)            \/
                       +---------------------------+
                       |    Staking Contract       |
                       |     (plus cw9 support)    |
                       |(validator/delegator split)|
                       +---------------------------+
```

## dPoE with Delegators

PoE -> dPoE presents a very similar challenge to Pos -> dPoS. The main differences are that:

1. The weights used to split between validators (reward splitter logic in option 2)
is no longer the registered as a group on the Staking Contract. We could add one more field
to set which contract we query to split (Option 1), or just wire up the distribution contract differently
(Option 2)

1. The major change is that the rewards are not split linearly between self-stake and delegation. Rather
the total rewards received by validator i (Ri) is split such that validator fraction is
`Vi = f(S, E) + c * [f(S + D, E) - f(S, E)] / f(S + D, E)` where S is self-stake and D is delegated stake.
Likewise the delegator fraction is `Di = (1-c) * [f(S + D, E) - f(S, E)]/ f(S + D, E)`. Lots of math there
which is only known to the PoE mixer, while the self-staking / delegation distribution is only known to
the staking module.

The second point will require us to once again consider more monolithic contracts (which makes composability
and extensibility more difficult), or consider more complex cross-contract queries to do so. Note that this formula
above also applies to the standard PoS module, just in the trivial case, where `f(S, E) = S`, such that it
reduces to: `Vi = S + c*D / (S+D)` and `Di = (1-c)*D / (S+D)`.

A monolithic implementation (Staking, Slashing, Delegator) is always doable. What requires research (and actual
code that implements some of the above subsystems) is to see how to build PoE with a generic PoS contract
without duplicating all that logic in two "similar but different" monoliths. In the end, this is not a horrible
solution, and actually a bit more loosely coupled than the current Cosmos SDK design, but the super composability of
the PoE without delegation encourages more design work to be done before implementation of this level begins.

## Conclusion

Above is a Roadmap from the simple multisig contracts of today to a modular, composable design for PoA, PoS, PoE with
and without delegatons, along with full integration to the native governance system and all staking contracts. There
are refinements that can be discovered along with way, but we present a clear step-by-step development path with
many concrete deliverables along the way that can be deployed to testnets and get real-world feedback and testing
without blocking on one giant epic.

This will be the most complex system constructed with CosmWasm and as a side-effect it will push us to enhance the
level of tooling to handle this level of complexity. Both to setup and connect graphs of contracts (init) as well
as to run realistic integration tests in pure Rust. It will also give us time to refine composition techniques
(smart queries, raw queries, directly importing code) and provide many examples to other CosmWasm developers who
wish to build complex contract systems. Thus, I can assume that the achievable architectural path as described here
will only be refined and simplified from the experience we gain with the first deliverables.
