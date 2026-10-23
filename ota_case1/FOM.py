import math

result = {'bandwidth':53.7e6, 'gain':55.83, 'cmrr':51.62, 'pm': 90.41}
target = {'bandwidth':1e6, 'gain':60, 'cmrr':80, 'pm': 60}
score = {}

for key,value in result.items():
    if value < target[key] :
         socre_ = 0.5 * (value / target[key])
         score[key] = socre_
    score[key] = (value / target[key])

for key,value in score.items():
    print(f'key:{key}, value:{value}')

FOM = math.pow(score['bandwidth'] * score['gain'] * score['cmrr'] * score['pm'], 1/4)
print(f'FOM = {FOM}')
