import yaml

files = [
    '.github/workflows/security-multi-scanner.yml', 
    '.github/workflows/ci.yml', 
    '.github/workflows/frontend-ci.yml', 
    '.github/workflows/backend-ci.yml'
]

for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            yaml.safe_load(file)
        print(f'{f}: OK')
    except yaml.YAMLError as e:
        print(f'{f}: {e}')
