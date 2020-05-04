import pymysql
import json

import pymysql.cursors
import json

import uuid

pymysql_exceptions = (
    pymysql.err.IntegrityError,
    pymysql.err.MySQLError,
    pymysql.err.ProgrammingError,
    pymysql.err.InternalError,
    pymysql.err.DatabaseError,
    pymysql.err.DataError,
    pymysql.err.InterfaceError,
    pymysql.err.NotSupportedError,
    pymysql.err.OperationalError)

default_db_params = {
    "dbhost": "localhost",                    # Changeable defaults in constructor
    "port": 3306,
    "dbname": "w4111final",
    "dbuser": "dbuser",
    "dbpw": "dbuserdbuser",
    "cursorClass": pymysql.cursors.DictCursor,        # Default setting for DB connections
    "charset":  'utf8mb4'                             # Do not change
}


def get_new_connection(params=default_db_params):
    cnx = pymysql.connect(
        host=params["dbhost"],
        port=params["port"],
        user=params["dbuser"],
        password=params["dbpw"],
        db=params["dbname"],
        charset=params["charset"],
        cursorclass=params["cursorClass"])
    return cnx


def run_q(cnx, q, args, fetch=False, commit=True, cursor=None):
    """
    :param cnx: The database connection to use.
    :param q: The query string to run.
    :param args: Parameters to insert into query template if q is a template.
    :param fetch: True if this query produces a result and the function should perform and return fetchall()
    :return:
    """
    #debug_message("run_q: q = " + q)
    #ut.debug_message("Q = " + q)
    #ut.debug_message("Args = ", args)

    result = None

    try:
        if cursor is None:
            cursor = cnx.cursor()

        result = cursor.execute(q, args)
        if fetch:
            result = cursor.fetchall()
        if commit:
            cnx.commit()
    except pymysql_exceptions as original_e:
        #print("dffutils.run_q got exception = ", original_e)
        if commit:
            cnx.rollback()
        raise(original_e)

    return result


def create_account(balance):
    """

    :param balance: The initial balance of the account.
    :return: None
    """

    # Just runs a quick, pessimistic locking transaction.
    cnx = get_new_connection()
    cur = cnx.cursor()
    cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE")

    # Generate a UUID for this version of the account state.
    version_id = str(uuid.uuid4())

    # Insert/create the new account record.
    q = "insert into w4111final.banking_account (balance, version) values(%s, %s)"
    result = run_q(cnx, q, (balance, version_id), fetch=True, commit=False)

    # By definition, we are in a transaction. So, auto-increment must be the largest value for
    # the auto-increment field.
    q = "select max(id) as new_id from w4111final.banking_account;"
    result = run_q(cnx, q, None, fetch=True, commit=False)

    result = result[0]['new_id']
    # Commit and free up resources.
    cnx.commit()
    cnx.close()

    return result



def get_balance(id, cursor=None):
    """

    Gets the balance for an account given an id. This call may be part of a larger transaction,
    and will receive a cursor if it is. Otherwise, cursor is None.
    :param id: The account number.
    :param cursor: Cursor for larger transaction, if any.
    :return:
    """

    cnx = None

    # I repeat this segment of code over and over again in each function just for clarity.
    # Normally, I would put in a function shared by all transactional functions. If I did this,
    # you would have to look through two functions to understand the logic.
    #
    # Is there already a cursor?
    if cursor is  None:

        # Not part of a bigger transaction. Create connection and cursor.
        cnx = get_new_connection()
        cursor = cnx.cursor()
        cursor_created = True
    else:
        cursor_created = False

    # Get the account balance.
    q = "select * from w4111final.banking_account where id=%s"
    result = run_q(cnx, q, id, fetch=True, commit=False, cursor=cursor)

    # Same comment as above. I repeat this over and over.
    # If this function created a cursor, clean up.
    # Otherwise, top-level transaction will do this.
    if cursor_created:
        cnx.commit()
        cnx.close()

    return result[0]['balance']


def get_account(id, cursor=None):

    if cursor is None:
        cnx = get_new_connection()
        cur = cnx.cursor()
        cursor_created = True
    else:
        cursor_created = False
        cnx = None

    q = "select * from w4111final.banking_account where id=%s"
    result = run_q(cnx, q, id, fetch=True, commit=False, cursor=cursor)

    if cursor_created:
        cnx.commit()
        cnx.close()

    return result[0]


def update_balance(id, amount, cursor=None):
    """

    :param id: Account number.
    :param amount: New balance to set.
    :param cursor: Cursor if part of a larger transaction. None otherwise.
    :return:
    """

    cnx = None

    # Connect and set up a transaction if I need one.
    if cursor is None:
        cnx = get_new_connection()
        cursor = cnx.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        cursor_created = True
    else:
        cursor_created = False

    # This function is going to change the data, and needs to modify version information.
    new_version = str(uuid.uuid4())

    # Update balance and version number.
    q = "update w4111final.banking_account set balance=%s, version=%s where id=%s"
    result = run_q(cnx, q, (amount, new_version, id), fetch=True, commit=False, cursor=cursor)

    if cursor_created:
        cnx.commit()
        cnx.close()


def update_balance_optimistic(acct, amount, cursor=None, cnx=None):
    if cursor is None:
        cnx = get_new_connection()
        cursor = cnx.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        cursor_created = True
    else:
        cursor_created = False
        cnx = None

    try:
        current_acct = get_account(acct['id'], cursor=cursor)
        if current_acct['version'] != acct['version']:
            raise ValueError("Optimistic transaction failed.")

        new_version = str(uuid.uuid4())

        q = "update w4111final.banking_account set balance=%s, version=%s where id=%s"

        result = run_q(cnx, q, (amount, new_version, acct['id']), fetch=True, commit=False, cursor=cursor)

        if cursor_created:
            cnx.commit()
            cnx.close()

        return result

    except Exception as e:
        print("Exception = ", e)
        if cursor_created:
            cnx.rollback()
            cnx.close()



def transfer_pessimistic():
    """
    Prompts for source and target accounts and amount to transfer.
    Locks accounts to prevent another update from interfering during the transfer.
    :return:
    """

    print(" \n*** Transfering Pessimistically ***\n")

    # Start the transaction that will contain individual operations.
    cnx = get_new_connection()
    cursor = cnx.cursor()

    try:
        # Prevent problems due to read/write conflicts between transactions.
        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

        # Get the source account information.
        source_id = input("Source account ID: ")

        # Get balance. Since we are passing a cursor, there will be a read lock on the account tuples.
        source_b = get_balance(source_id, cursor=cursor)

        # I do these prompts this way to slow down the transaction so that we can play with various conflicts.
        cont = input("Source balance = " + str(source_b) + ". Continue (y/n)")

        if cont == 'y':

            # Same logic but for target.
            target_id = input("Target account ID: ")
            target_b = get_balance(target_id, cursor=cursor)
            input("Target balance = " + str(target_b) + ". Continue (y/n)")

            if cont == 'y':

                amount = input("Amount: ")
                amount = float(amount)

                # Compute new balances.
                new_source = source_b - amount
                new_target = target_b + amount

                # Perform updates.
                update_balance(source_id, new_source, cursor=cursor)
                update_balance(target_id, new_target, cursor=cursor)

                cnx.commit()
                cnx.close()

    except Exception as e:
        print("Got exception = ", e)
        cnx.rollback()
        cnx.close()

    return


def transfer_optimistic():
    """
    Same as above, but optimistic.
    :return:
    """

    print(" \n*** Transfering Optimistically *** \n")

    source_id = input("Source account ID: ")

    # Do not pass a cursor. Read should read, commit and release locks.
    source_acct = get_account(source_id, cursor=None)
    cont = input("Source balance = " + str(source_acct['balance']) + ". Continue (y/n)")

    if cont == 'y':

        # Same basic logic.
        target_id = input("Target account ID: ")
        target_acct = get_account(target_id, cursor=None)
        input("Target balance = " + str(target_acct['balance']) + ". Continue (y/n)")

        if cont == 'y':

            amount = input("Amount: ")
            amount = float(amount)

            # Compute new balances.
            new_source = source_acct['balance'] - amount
            new_target = target_acct['balance'] + amount

            try:
                # Begin a transaction to perform transfer.

                cnx = get_new_connection()
                cursor = cnx.cursor()
                cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

                # Update the balances. This will fail if underlying balance has changed.
                update_balance_optimistic(source_acct, new_source, cursor=cursor, cnx=cnx)
                update_balance_optimistic(target_acct, new_target, cursor=cursor, cnx=cnx)

                cnx.commit()
                cnx.close()
            except Exception as e:
                print("Got exception = ", e)
                cnx.rollback()
                cnx.close()

        return



