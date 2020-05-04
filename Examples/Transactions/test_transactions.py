import sys

sys.path.append("/Users/donaldferguson/Dropbox/ColumbiaCourse/Courses/W4111New/w4111-Databases")

import Transactions.trans_final as trans_final

choice = input("Transfer optimistically (=1) or pessimistically? (=2)")
if choice == '1':
    trans_final.transfer_optimistic()
else:
    trans_final.transfer_pessimistic()


