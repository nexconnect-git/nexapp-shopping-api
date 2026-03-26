import os
import re

base_path = r'd:\Projects\NexConnect\shopping-app\backend'
apps = ['accounts', 'vendors', 'products', 'delivery', 'orders', 'notifications']

# Inject UUIDs into Models
for app in apps:
    models_path = os.path.join(base_path, app, 'models.py')
    with open(models_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'import uuid' not in content:
        content = 'import uuid\n' + content

    def replacer(match):
        return match.group(0) + "\n    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)"

    # don't inject if it already has id = models.UUIDField
    if 'id = models.UUIDField' not in content:
        new_content = re.sub(r'class \w+\(models\.Model\):|class \w+\(AbstractUser\):', replacer, content)
        with open(models_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

# Delete SQLite DB
db_path = os.path.join(base_path, 'db.sqlite3')
if os.path.exists(db_path):
    os.remove(db_path)
    print("Deleted db.sqlite3")

# Delete migration files
for app in apps:
    mig_dir = os.path.join(base_path, app, 'migrations')
    if os.path.exists(mig_dir):
        for f in os.listdir(mig_dir):
            if f != '__init__.py' and f.endswith('.py'):
                os.remove(os.path.join(mig_dir, f))
                print(f"Deleted {app}/migrations/{f}")

print("UUID script run successfully.")
