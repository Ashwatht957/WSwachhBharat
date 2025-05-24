import psycopg2

staff_url = 'postgresql://neondb_owner:npg_64pzLnOdiYEm@ep-summer-rice-a11qf6db-pooler.ap-southeast-1.aws.neon.tech/staff?sslmode=require'
location_url = 'postgresql://neondb_owner:npg_64pzLnOdiYEm@ep-summer-rice-a11qf6db-pooler.ap-southeast-1.aws.neon.tech/location?sslmode=require'


try:
    conn = psycopg2.connect(staff_url)
    print("Staff DB connected successfully")
    conn.close()
except Exception as e:
    print(f"Staff DB connection failed: {e}")

try:
    conn = psycopg2.connect(location_url)
    print("Location DB connected successfully")
    conn.close()
except Exception as e:
    print(f"Location DB connection failed: {e}")
