import re
import sqlite3

regex = re.compile(r'^[A-Za-z0-9._-]+$')

def check_data(data, regex):
    id = data[0]
    nearest = data[1]
    assoc = data[2]
    ensg = data[3]

    s0 = f'ID: {id} '
    s1 = f'Nearest: {nearest} ' if nearest and not regex.match(nearest) else ''
    s2 = f'Associated: {assoc} ' if assoc and not regex.match(assoc) else ''
    s3 = f'Ensg: {ensg} ' if ensg and not regex.match(ensg) else ''

    if any([s1, s2, s3]):
        print(s0 + s1 + s2 + s3)


con = sqlite3.connect("./database/local.sqlite3")
cur = con.cursor()
res = cur.execute('select id, lead_variant_nearest_gene, lead_variant_assoc_gene, lead_variant_assoc_gene_ensg from core_marginalsignal')
for row in res:
    check_data(row, regex)
con.close()
