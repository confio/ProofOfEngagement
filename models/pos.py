def calculate_voting_weight(validator, params=None):
    self_stake = validator['self_stake']
    delegation = validator['delegation']

    return self_stake + delegation


def calculate_reward(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    self_stake = validator['self_stake']
    commission_rate = validator['commission_rate']
    delegation = validator['delegation']

    return inflation_rate * (self_stake + commission_rate * delegation) / total_voting_weight


def calculate_yield(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    commission_rate = validator['commission_rate']

    return inflation_rate * (1 - commission_rate) / total_voting_weight
