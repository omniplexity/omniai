import sqlite3

# Password hash generated earlier
password_hash = "$argon2id$v=19$m=65536,t=3,p=4$GEzmLfWwIuQAl97COHJQ5Q$amK38pzJycu3nXSlWOXOzE2jfUaPc68Qltqq2aWcU+U"

conn = sqlite3.connect('/app/.data/omni.db')
cursor = conn.cursor()

# Update password for Omni user
cursor.execute(
    "UPDATE auth_identities SET password_hash = ? WHERE username = ?",
    (password_hash, 'Omni')
)

conn.commit()
print('Updated password for Omni user')

# Verify
cursor.execute('SELECT user_id, username, password_hash FROM auth_identities WHERE username = ?', ('Omni',))
result = cursor.fetchone()
print(f'Identity: {result[0]}, {result[1]}')
print(f'Hash: {result[2][:50]}...')
