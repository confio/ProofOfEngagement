def calculate_voting_weight(validator, params=None):
    return validator.self_stake + validator.delegation


def calculate_reward(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    return inflation_rate * (validator.self_stake + validator.commission_rate * validator.delegation) / total_voting_weight


def calculate_yield(validator, total_voting_weight, params):
    inflation_rate = params['inflation_rate']
    return inflation_rate * (1 - validator.commission_rate) / total_voting_weight
