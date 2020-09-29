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


def create_validator(
    i,
    commission_rate,
    self_stake_base,
    self_stake_max,
    engagement_base,
    engagement_max,
    delegation=0
):
    self_stake = self_stake_max * self_stake_base**i
    engagement = engagement_max * engagement_base**i
    return {
        'commission_rate': commission_rate,
        'self_stake': self_stake,
        'engagement': engagement,
        # redundant state (can be calculated from state of delegators)
        'delegation': delegation,
    }


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
    validators = [create_validator(
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
        engagements = [validator['engagement'] for validator in validators]
        random.shuffle(engagements)
        for i, validator in enumerate(validators):
            validator['engagement'] = engagements[i]

    return validators


def create_delegator(delegation, validator_index=None):
    return {
        'delegation': delegation,
        'validator': validator_index,
    }


def create_delegators(n_delegators, validators, delegation_stake_multiple):
    sum_validators_self_stake = sum(
        [validator['self_stake'] for validator in validators])
    delegation = delegation_stake_multiple * \
        sum_validators_self_stake / n_delegators
    return [create_delegator(delegation) for _ in range(n_delegators)]


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
    current_validator_index = delegator['validator']
    delegation = delegator['delegation']

    if current_validator_index == validator_index:
        total_voting_weight = calculate_total_voting_weight(
            validators, params)
        return calculate_yield(validators[current_validator_index], total_voting_weight, params)

    if current_validator_index != None:
        validators[current_validator_index]['delegation'] -= delegation

    next_validator = validators[validator_index]
    next_validator['delegation'] += delegation
    total_voting_weight = calculate_total_voting_weight(
        validators, params)

    return calculate_yield(next_validator, total_voting_weight, params)
