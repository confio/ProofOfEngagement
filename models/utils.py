import copy
import random
import statistics

import poe
import pos


def calculate_gini_coefficient(x):
    '''A measure of inequality. 0 is total equality, 1 is total inequality.
    Note that the result can exceed these bounds if the inputs include negative numbers.
    '''
    numerator = sum([sum([abs(i - j) for j in x]) for i in x])

    n = len(x)
    x_bar = statistics.mean(x)
    denominator = 2 * n**2 * x_bar

    return numerator / denominator


class Validator:
    def __init__(self, i, commission_rate, self_stake_base, self_stake_max, engagement_base, engagement_max, delegation=0):
        self.commission_rate = commission_rate
        self.self_stake = self_stake_max * self_stake_base**i
        self.engagement = engagement_max * engagement_base**i
        # redundant state (can be calculated from state of delegators)
        self.delegation = delegation


def create_validators(
    n,
    commission_rate,
    self_stake_base,
    self_stake_max,
    engagement_base,
    engagement_max,
    delegation=0,
    shuffle_engagements=True
):
    validators = [Validator(
        i,
        commission_rate,
        self_stake_base,
        self_stake_max,
        engagement_base,
        engagement_max,
        delegation,
    ) for i in range(n)]
    validators.reverse()

    if shuffle_engagements:
        engagements = [validator.engagement for validator in validators]
        random.shuffle(engagements)
        for i, validator in enumerate(validators):
            validator.engagement = engagements[i]

    return validators


class Delegator:
    def __init__(self, delegation, validator_index=None):
        self.delegation = delegation
        self.validator = validator_index


def create_delegators(n_delegators, validators, delegation_stake_multiple):
    sum_validators_self_stake = sum(
        [validator.self_stake for validator in validators]
    )
    delegation = delegation_stake_multiple * \
        sum_validators_self_stake / n_delegators
    return [Delegator(delegation) for _ in range(n_delegators)]


def calculate_voting_weight(validator, params):
    consensus_algorithm = params['consensus_algorithm']

    if consensus_algorithm == 'PoE':
        return poe.calculate_voting_weight(validator, params)
    if consensus_algorithm == 'PoS':
        return pos.calculate_voting_weight(validator, params)

    raise ValueError('Consensus algorithm not known')


def calculate_total_voting_weight(validators, params):
    return sum([calculate_voting_weight(validator, params) for validator in validators])


def calculate_reward(validator, total_voting_weight, params):
    consensus_algorithm = params['consensus_algorithm']

    if consensus_algorithm == 'PoE':
        return poe.calculate_reward(validator, total_voting_weight, params)
    if consensus_algorithm == 'PoS':
        return pos.calculate_reward(validator, total_voting_weight, params)

    raise ValueError('Consensus algorithm not known')


def calculate_yield(validator, total_voting_weight, params):
    consensus_algorithm = params['consensus_algorithm']

    if consensus_algorithm == 'PoE':
        return poe.calculate_yield(validator, total_voting_weight, params)
    if consensus_algorithm == 'PoS':
        return pos.calculate_yield(validator, total_voting_weight, params)

    raise ValueError('Consensus algorithm not known')


def hypothesize_yield(delegator, validator_index, validators, params):
    hypothetical_validators = copy.deepcopy(validators)
    current_validator_index = delegator.validator
    delegation = delegator.delegation

    if current_validator_index == validator_index:
        total_voting_weight = calculate_total_voting_weight(
            hypothetical_validators, params)
        return calculate_yield(hypothetical_validators[current_validator_index], total_voting_weight, params)

    if current_validator_index != None:
        hypothetical_validators[current_validator_index].delegation -= delegation

    next_validator = hypothetical_validators[validator_index]
    next_validator.delegation += delegation
    total_voting_weight = calculate_total_voting_weight(
        hypothetical_validators, params)

    return calculate_yield(next_validator, total_voting_weight, params)
