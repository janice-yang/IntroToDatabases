import sqlite3
import requests
import json


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Exception as e:
        print(e)

    return conn


def add_country(c_data):
    try:
        sql_statement = """INSERT INTO country_standards(alpha2code, alpha3code, name) 
            VALUES(?, ?, ?)"""
        conn = create_connection('countries.db')
        print("Conn = ", conn)
        cur = conn.cursor()
        result = cur.execute(sql_statement, c_data)
    except Exception as e:
        print("Exception e = ", e)
        result = None

    conn.commit()
    conn.close()

    return result


def get_country_info(c_name, fields=None):
    url = "https://restcountries.eu/rest/v2/name/" + c_name

    if fields is not None:
        field_query = ";".join(fields)
        url += "?fields=" + field_query

    result = requests.get(url)

    if result.status_code != 200:
        result = None
    else:
        result = result.json()

    return result


def create_tables():

    sql = []
    sql.append("drop table if exists country_standards;")
    sql2 = """create table country_standards(
            alpha2code char(2) primary key,
            alpha3code char(3),
            name varchar(256));
        """
    sql.append(sql2)

    conn = create_connection("countries.db")
    cur = conn.cursor()

    for s in sql:
        res = cur.execute(s)

    conn.commit()
    conn.close()


def t1():

    create_tables()

    c_info = get_country_info('United States', fields=['name', 'alpha2Code', 'alpha3Code',
                                            'callingCodes', 'altSpellings'])
    print("Result = ")
    print(json.dumps(c_info, indent=2))

    for c in c_info:
        to_add = [c['alpha2Code'], c['alpha3Code'], c['name']]
        res = add_country(to_add)
        print("Add result = ", res)



t1()
