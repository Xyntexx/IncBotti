import datetime
from botocore.exceptions import ClientError

TIL = 60 * 60 * 24

now = datetime.datetime.now


class IncTable:

    def __init__(self, dynamodb, log):

        log.info("Container Created")
        self.log = log
        if dynamodb is not None:
            self.Inctable_long = dynamodb.Table('Inctable2')
            self.Inctable_short = dynamodb.Table('Inctable1')
        self.db_long = {}
        self.db_short = {}

    def __del__(self):
        self.log.info("Container destroyed")

    def get_short(self, chat_id):
        if chat_id not in self.db_short:
            resp = self.Inctable_short.query(
                ExpressionAttributeValues={":id": chat_id},
                KeyConditionExpression='chatid = :id')
            self.db_short[chat_id] = resp["Items"]
        return [i for i in self.db_short[chat_id] if i["expire"] >= datetime.datetime.now().timestamp()]

    def update_short(self, chat_id, user_id, inc):
        items = self.get_short(chat_id)
        time = int(datetime.datetime.now().timestamp())
        while True:
            for i in items:
                if i["userid"] == user_id and i["expire"] == time + TIL:
                    time += 1
                    continue
            break

        item = {
            'chatid': chat_id,
            'expire': time + TIL,
            'userid': user_id,
            'inc': inc
        }
        resp = self.Inctable_short.put_item(
            Item=item, ConditionExpression='attribute_not_exists(chatid) AND attribute_not_exists(expire)')
        self.db_short[chat_id].append(item)

    def update_long(self, chat_id, user_id, inc):

        resp = self.Inctable_long.update_item(
            Key={
                'chatid': chat_id,
                'userid': user_id
            },
            UpdateExpression="set inc = inc + :val",
            ExpressionAttributeValues={
                ':val': inc
            },
            ReturnValues="UPDATED_NEW")
        self.db_long[chat_id][user_id]["inc"] += inc
        return self.db_long[chat_id][user_id]

    def reset_user(self, chat_id, user_id):
        self.log.warning((chat_id, user_id))
        resp = self.Inctable_long.update_item(
            Key={
                'chatid': chat_id,
                'userid': user_id
            },
            UpdateExpression="set inc = :val",
            ExpressionAttributeValues={
                ':val': 0
            },
            ReturnValues="UPDATED_NEW")
        self.db_long[chat_id][user_id]["inc"] = 0
        return self.db_long[chat_id][user_id]

    def set_year(self, chat_id, year):
        resp = self.Inctable_long.update_item(
            Key={
                'chatid': chat_id,
                'userid': 0
            },
            UpdateExpression="set lastyear = :val",
            ExpressionAttributeValues={
                ':val': year
            },
            ReturnValues="UPDATED_NEW")
        self.db_long[chat_id][0]["lastyear"] = year

    def put_long(self, chat_id, item):
        if not self.db_long.get(chat_id):
            self.db_long[chat_id] = {}
        self.db_long[chat_id][item["userid"]] = item
        self.Inctable_long.put_item(Item=item)

    def check_year(self, chat_id, items):
        current_year = (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).year
        saved_year = items[0].get("lastyear")
        if not saved_year:
            self.log.warning('"lastyear" is empty')
            self.set_year(chat_id, current_year)
            saved_year = 0
        if current_year > saved_year:
            self.log.warning("Current year has changed. Happy new year {}. Reseting user values".format(current_year))
            self.log.warning(items)
            for i in items:
                if i == 0:
                    pass
                else:
                    self.reset_user(chat_id, i)
            self.set_year(chat_id, current_year)

    def get_long(self, chat_id) -> dict:

        if chat_id not in self.db_long:
            resp = self.Inctable_long.query(ExpressionAttributeValues={":id": chat_id},
                                            KeyConditionExpression='chatid = :id ')
            adict = {i.get("userid"): i for i in resp["Items"]}
            self.db_long[chat_id] = adict
        self.check_year(chat_id, self.db_long[chat_id])
        return self.db_long[chat_id]