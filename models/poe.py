import math


def default_sigmoidal(stake, engagement):
    return 2000 / (1 + math.exp(-0.000001 * (stake * engagement)**0.68)) - 1000


def calculate_voting_weight(validator, params):
    f = params['f']
    self_stake = validator['self_stake']
    delegation = validator['delegation']
    engagement = validator['engagement']

    return f(self_stake + delegation, engagement)


def calculate_reward(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    f = params['f']
    self_stake = validator['self_stake']
    engagement = validator['engagement']
    commission_rate = validator['commission_rate']

    voting_weight = calculate_voting_weight(validator, params)
    self_stake_voting_weight = f(self_stake, engagement)

    return inflation_rate * (self_stake_voting_weight + commission_rate * (voting_weight - self_stake_voting_weight)) / total_voting_weight


def calculate_yield(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    f = params['f']
    commission_rate = validator['commission_rate']
    self_stake = validator['self_stake']
    engagement = validator['engagement']
    delegation = validator['delegation']

    if delegation == 0:
        return 0

    voting_weight = calculate_voting_weight(validator, params)
    self_stake_voting_weight = f(self_stake, engagement)

    return (inflation_rate * (1 - commission_rate) * (voting_weight - self_stake_voting_weight)) / (delegation * total_voting_weight)
