import sqlite3

password_hash = "$argon2id$v=19$m=65536,t=3,p=4$Hq3N1sdP2F5Sa6pVfvIFHA$uu5D9ykOT0UPQARgUVedibqMAvd0j8pRnhAtJD7KhGg"

conn = sqlite3.connect('/app/.data/omni.db')
cursor = conn.cursor()
cursor.execute('UPDATE auth_identities SET password_hash = ? WHERE username = ?', (password_hash, 'Omni'))
conn.commit()
print('Updated Omni user password')

cursor.execute('SELECT user_id, username, password_hash FROM auth_identities WHERE username = ?', ('Omni',))
result = cursor.fetchone()
print(f'User: {result[0]}, {result[1]}')
print(f'Hash: {result[2][:60]}...')
