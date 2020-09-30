import math


def default_sigmoidal(stake, engagement):
    return 2000 / (1 + math.exp(-0.000001 * (stake * engagement)**0.68)) - 1000


def calculate_voting_weight(validator, params):
    f = params['f']
    return f(validator.self_stake + validator.delegation, validator.engagement)


def calculate_reward(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    f = params['f']

    voting_weight = calculate_voting_weight(validator, params)
    self_stake_voting_weight = f(validator.self_stake, validator.engagement)

    return inflation_rate * (self_stake_voting_weight + validator.commission_rate * (voting_weight - self_stake_voting_weight)) / total_voting_weight


def calculate_yield(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    f = params['f']

    if validator.delegation == 0:
        return 0

    voting_weight = calculate_voting_weight(validator, params)
    self_stake_voting_weight = f(validator.self_stake, validator.engagement)

    return (inflation_rate * (1 - validator.commission_rate) * (voting_weight - self_stake_voting_weight)) / (validator.delegation * total_voting_weight)
