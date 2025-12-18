import psycopg2
conn = psycopg2.connect("postgresql://postgres:MfxAqmdsoKRvATHsVcRinyMaFgwteIpT@ballast.proxy.rlwy.net:57684/railway", connect_timeout=5)
print("connected", conn.dsn)
conn.close()