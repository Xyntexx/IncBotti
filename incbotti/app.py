import datetime
import decimal
import json
import logging
import os
import random
import requests
import boto3
import inctable

# inc1 - inccaus
# dec1 - deccaus
# leaderboard - leaderboard
# stats - stats
# 24h - 24h inccaukset
# incryys-  random inccaus 1-5 voit listätä kertoimen. esim /incryys 3

MAX_KERROIN = 5
TESTING = False

logger = logging.getLogger()
logger.setLevel(logging.INFO)
if TESTING:
    def testrequests(url):
        print("GET URL: " + url)
        pass


    def debug(*obj):
        print(obj)
        logger.debug(obj)


    logger.setLevel(logging.DEBUG)
    debug("Logging lever Debug")
    os.environ['BotAPI'] = "xxxxxxxxxxxxxx"
    os.environ['STIKKERI'] = "xxxxxxxxxxx"

    requests.get = testrequests
else:
    logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = inctable.IncTable(dynamodb, logger)

TELE_TOKEN = os.environ['BotAPI']
URL = "https://api.telegram.org/bot{}/".format(TELE_TOKEN)

now = datetime.datetime.now

STIKKERI = os.environ['STIKKERI']


class DecimalEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def getFirst(elem):
    return elem[0]


def getInt(in_sting):
    try:
        return int(in_sting)
    except ValueError:
        return 1


def get_string(in_sting):
    return in_sting.strip()


def h24_list(chat_id) -> (int, list):
    items = table.get_short(chat_id)

    inc_all = 0

    dicti = {}
    for i in items:
        inc_all += i['inc']
        if i["userid"] in dicti:
            dicti[i["userid"]]["inc"] += getInt(i['inc'])
        else:
            dicti[i["userid"]] = {}
            dicti[i["userid"]]["inc"] = getInt(i['inc'])
            dicti[i["userid"]]["name"] = get_name(chat_id, i["userid"])
    users = []
    for i in dicti:
        users.append((i, dicti[i]))
        users.sort(key=lambda e: e[1].get("inc"), reverse=True)
    return inc_all, users


def h24msg(chat_id):
    inc_all, users = h24_list(chat_id)
    lines = []
    for i in users:
        if i[0] != 0:
            lines.append(str(users.index(i) + 1) + ". " + i[1]["name"] + ": " + str(getInt(i[1]["inc"])))
    first = "Last 24h: \nall: {} \n".format(inc_all)
    message = "\n".join(lines)
    return first + message


def h24_incs(chat_id, user_id):
    inc_all, users = h24_list(chat_id)
    if user_id == 0:
        return inc_all
    else:
        return next((i[1]["inc"] for i in users if i[0] == user_id), 0)


def inc(chat_id, user_id, name, args):
    if len(args) == 0:
        count = 1
    elif len(args[0]) > 10:
        count = 1
    else:
        count = getInt(args[0])
    incs_all = table.update_long(chat_id, 0, count)
    incs = table.update_long(chat_id, user_id, count)
    table.update_short(chat_id, user_id, count)

    send_message("All: {} {}: {}".format(incs_all["inc"], name, incs["inc"]), chat_id)


def dec(chat_id, user_id, name, args):
    if len(args) == 0:
        count = -1
    else:
        count = -getInt(args[0])
    incs_all = table.update_long(chat_id, 0, count)
    incs = table.update_long(chat_id, user_id, count)
    table.update_short(chat_id, user_id, count)

    send_message("All: {} {}: {}".format(incs_all["inc"], name, incs["inc"]), chat_id)


def check_new_chat(chat_id):
    items = table.get_long(chat_id)
    if not items:
        resp = table.put_long(chat_id,
                              {
                                  'chatid': chat_id,
                                  'userid': 0,
                                  'inc': 0,
                                  'name': 'all',
                                  'first_date': now().strftime("%y%m%d"),
                                  'lastyear': (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).year
                              })
        send_sticker(STIKKERI, chat_id)


def get_name(chat_id, user_id):
    items = table.get_long(chat_id)
    return next((items[i].get("name") for i in items if items[i].get("userid") == user_id), "noname")


def check_new_user(chat_id, user_id, first_name, last_name):
    items = table.get_long(chat_id)
    name = (first_name + last_name[0]) if len(last_name) > 0 else first_name
    if user_id not in items:
        table.put_long(chat_id, {
            'chatid': chat_id,
            'userid': user_id,
            'name': name,
            'inc': 0,
            'first_date': int(now().strftime("%y%m%d")),
        })
        check_new_chat(chat_id)
        send_message('Uusi käyttäjä: ' + first_name + last_name[0], chat_id)
    return name


def stats(chat_id, user_id, args):
    items = table.get_long(chat_id)
    if len(args) == 0:
        pass
    elif args[0] in ["all", "All", "ALL"]:
        user_id = 0
    else:
        user_id = next((i for i in items if items[i].get("name") == args[0]), None)

    if user_id is None:
        msg = "Name: " + args[0] + " not found"
        send_message(msg, chat_id)
        return

    user_data = items[user_id]
    name = user_data['name']
    first_date = str(user_data['first_date'])
    date_object = datetime.datetime.strptime(first_date, "%y%m%d")
    if date_object.year < now().year:
        new_years_eve = datetime.datetime(now().year, 1, 1, 0, 0, 0)
        time = now() - new_years_eve
    else:
        time = now() - date_object
    days = time.days
    incs = user_data['inc']
    if days == 0:
        days = 1

    incs_per_day = float(incs) / days
    last24h = h24_incs(chat_id, user_id)
    message = "{} Incs: {}. Incs per day: {:.2f}\nLast 24h: {}".format(name, incs, incs_per_day, last24h)
    send_message(message, chat_id)


def leaderboard(chat_id):
    users = []
    all_str = ""
    total = 0
    items = table.get_long(chat_id)
    for i in items:
        if i == 0:
            all_str = "All: {}".format(int(items[i]['inc']))
        else:
            total += int(items[i]['inc'])
            users.append((int(items[i]['inc']), items[i]['name']))
    year = str((datetime.datetime.utcnow() + datetime.timedelta(hours=2)).year) + " :\nAll: {}".format(total)
    users.sort(key=getFirst, reverse=True)
    lines = []

    for i in users:
        if i[0] != 0:
            lines.append(str(users.index(i) + 1) + ". " + i[1] + ": " + str(i[0]))

    message = all_str + "\n" + year + "\n" + "\n".join(lines)

    send_message(message, chat_id)


def send_message(text, chat_id):
    url = URL + "sendMessage?text={}&chat_id={}".format(text, chat_id)
    requests.get(url)


def send_sticker(sticker, chat_id):
    url = URL + "sendSticker?sticker={}&chat_id={}".format(sticker, chat_id)
    requests.get(url)


def incryys(chat_id, user_id, name, args):
    random.seed()
    if len(args) == 0:
        kerroin = 1
    else:
        kerroin = getInt(args[0])
    if kerroin > MAX_KERROIN:
        send_message("Max kerroin " + str(MAX_KERROIN), chat_id)
        kerroin = 5
    if kerroin < 1:
        send_message("Kerroin oltava positiivinen kokonaisluku", chat_id)
        kerroin = 1
    incs = random.randrange(1, 6) * kerroin
    send_message("Ryys: {}".format(incs), chat_id)
    inc(chat_id, user_id, name, [incs])


def lambda_handler(event, context):
    if event['path'] == '/Incbotti/insert':
        return {'statusCode': 501}
    event_body = json.loads(event['body'])
    message = event_body.get('message')
    if not message:
        return {'statusCode': 200}
    chat_id = message['chat']['id']
    user_id = message['from']['id']
    first_name = message['from']['first_name']
    last_name = message['from']['last_name'] if 'last_name' in message['from'] else ""
    message_text = message.get('text')
    if not message_text:
        return {'statusCode': 200}
    message_text = message_text.split("@")[0]
    command, *args = message_text.strip().split(" ")
    logger.info(command + " " + str(args))
    if command.startswith("/leaderboard"):
        name = check_new_user(chat_id, user_id, first_name, last_name)
        leaderboard(chat_id)
    elif command.startswith("/stats"):
        name = check_new_user(chat_id, user_id, first_name, last_name)
        stats(chat_id, user_id, args)
    elif command.startswith("/inc1") or command.startswith("/INC1"):
        name = check_new_user(chat_id, user_id, first_name, last_name)
        inc(chat_id, user_id, name, args)
    elif command.startswith("/dec1"):
        name = check_new_user(chat_id, user_id, first_name, last_name)
        dec(chat_id, user_id, name, args)
    elif command.startswith("/24"):
        last24 = h24msg(chat_id)
        send_message(last24, chat_id)
    elif command.startswith("/incryys"):
        name = check_new_user(chat_id, user_id, first_name, last_name)
        incryys(chat_id, user_id, name, args)
    if TESTING:
        return {'statusCode': 0}
    else:
        return {'statusCode': 200}
