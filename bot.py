"""
Commands: reg, add, remove, check, log
Usage:
/reg
/add <value> <comment> [username percent, ]
/check <check_id>
/log [-m [month]] [-a]

"""
# TODO: выложить на github

import config
import telebot
import sqlite3

if hasattr(config, 'proxy_server'):
    telebot.apihelper.proxy = config.proxy_server

bot = telebot.TeleBot(config.access_token)
bot_name = bot.get_me().username


def create_tables():
    with sqlite3.connect("database.sqlite") as conn:
        c = conn.cursor()
        c.execute('drop table user')
        c.execute('drop table cost')
        c.execute('drop table split')
        c.execute('''create table if not exists user(
u_id integer primary key,
name text not null
);''')
        c.execute('''create table if not exists cost(
c_id integer primary key autoincrement,
u_id integer,
comment text, 
value integer not null,
date integer,
members integer not null,
foreign key(u_id) references user(u_id)
);''')
        c.execute('''create table if not exists split(
c_id integer,
u_id integer,
proc float not null,
fin_value integer not null,
foreign key(u_id) references user(u_id),
foreign key(c_id) references cost(c_id)
);''')


# create_tables()


def get_date(val, month='01.2020', rel=-1, date=None):
    import datetime
    import dateutil.relativedelta
    now = datetime.datetime.now()
    if val == 'now_full':
        return now.strftime("%y-%m-%d %H:%M")
    elif val == 'prev_month':
        prev_month = (now + dateutil.relativedelta.relativedelta(months=-1))
        return prev_month.strftime("%y-%m-%d %H:%M")
    elif val == 'spec_month':
        spec_month = datetime.datetime.strptime(month, '%m.%Y')
        return spec_month.strftime("%y-%m-%d %H:%M")
    elif val == 'relative':
        prev_month = (date + dateutil.relativedelta.relativedelta(months=rel))
        return prev_month.strftime("%y-%m-%d %H:%M")


@bot.message_handler(commands=['reg'])
def command_reg(message):
    with sqlite3.connect("database.sqlite") as conn:
        uid = message.from_user.id
        c = conn.cursor()
        bol = conn.cursor().execute('''select count(u_id) from user where u_id = ?''', (str(uid),)).fetchone()[0]
        if bol == 0:
            c.execute('''insert into user values (?, ?)''', (str(uid), message.from_user.first_name))
            bot.send_message(message.chat.id, 'Пользователь %d успешно зарегистрирован' % (uid,))
        else:
            c.execute('''update user set name = ? where u_id = ?''', (message.from_user.first_name, str(uid)))
            bot.send_message(message.chat.id, 'Данные обновлены!')
        conn.commit()


@bot.message_handler(commands=['add'])
def command_add(message):
    with sqlite3.connect("database.sqlite") as conn:
        if len(message.text.split()) == 3:
            c = conn.cursor()
            uid = message.from_user.id
            (m_val, m_com) = message.text.split()[1:]
            m_date = get_date('now_full')
            cnt = c.execute('select count(u_id) from user').fetchone()[0]
            c.execute('''insert into cost(u_id, comment, value, date, members) values(?, ?, ?, ?, ?)''',
                      (str(uid), m_com, str(m_val), str(m_date), str(cnt)))
            m_cid = c.execute('select c_id from cost order by c_id desc limit 1').fetchone()[0]
            m_proc = 1/cnt
            for item in c.execute('select u_id from user').fetchall():
                c.execute('''insert into split(c_id, u_id, proc, fin_value) values(?, ?, ?, ?)''',
                          (str(m_cid), str(item[0]), str(m_proc), str(int(m_val) * m_proc)))
            bot.send_message(message.chat.id, 'Чек на сумму %sр. успешно добавлен' % (str(m_val),))
        elif len(message.text.split() > 3):
            pass    # TODO: Добавить разделение между кастомным количеством людей
        conn.commit()


@bot.message_handler(commands=['remove'])
def command_remove(message):
    with sqlite3.connect("database.sqlite") as conn:
        c = conn.cursor()
        c_id = message.text.split()[1]
        c.execute('''delete from split where c_id == ?''', (str(c_id),))
        c.execute('''delete from cost where c_id == ?''', (str(c_id),))
        bot.send_message(message.chat.id, 'Чек №%s успешно удалён' % (str(c_id),))
        conn.commit()


@bot.message_handler(commands=['check'])
def command_check(message):
    with sqlite3.connect("database.sqlite") as conn:
        c = conn.cursor()
        c_id = message.text.split()[1] if message.text.strip() != '/check' else 0
        if c.execute('''select count(u_id) from cost where c_id == ?''', (str(c_id),)).fetchone()[0] != 0:
            (m_uid, m_com, m_val, m_date, m_mem) = c.execute('''select u_id, comment, value, date, members from cost 
                                                                where c_id == ?''', str(c_id)).fetchone()
            (m_nick,) = c.execute('select name from user where u_id == ?', (str(m_uid),)).fetchone()
            text = 'Чек №%s на сумму %sр.\n%s потратил свои деньги на %s.\n' % (c_id, m_val, m_nick, m_com)
            for item in c.execute('select u_id, proc, fin_value from split where c_id == ?', (str(c_id),)).fetchall():
                (u_nick,) = c.execute('select name from user where u_id == ?', (str(item[0]),)).fetchone()
                text = text + '%s потратил %.f процентов\n' % (u_nick, item[1]*100)
            text = text + m_date
            bot.send_message(message.chat.id, text)
        else:
            text = 'Такого чека не существует :('
            bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['log'])
def command_log(message):
    with sqlite3.connect("database.sqlite") as conn:
        c = conn.cursor()
        if len(message.text.split()) == 1:
            text = 'Краткий лог:\n'
            for user in c.execute('''select u_id, name from user''').fetchall():
                u_id = user[0]
                name = user[1]
                user_count = c.execute('''select count(u_id) from user''').fetchone()[0]
                full_sum = c.execute('''select sum(fin_value) from split where u_id == ?''', (u_id, )).fetchone()[0]
                relative_sum = (c.execute('''select sum(fin_value) from split''').fetchone()[0]/user_count) - full_sum
                text += '[%s] %s - %sр. (%s)\n' % (u_id, name, full_sum, relative_sum)
            bot.send_message(message.chat.id, text)
        elif message.text.split()[1] in ['-m', '--month']:
            if len(message.text.split()) == 2:
                text = 'Лог за месяц:\n'
                for item in c.execute('''select c_id, u_id, comment, value, date, members from cost 
                                    where date > ? order by date desc''', (get_date('prev_month'),)).fetchall():
                    (m_cid, m_uid, m_com, m_val, m_dat, m_mem) = item
                    m_name = c.execute('select name from user where u_id = ?', (m_uid,)).fetchone()[0]
                    text = text + '#%s [%s] %sр(|%s) - %s \t(%s)\n' % (m_cid, m_name, m_val, m_mem, m_com, m_dat)
                bot.send_message(message.chat.id, text)
            elif len(message.text.split()) == 3:
                lower_date = get_date('spec_month', month=message.text.split[2])
                upper_date = get_date('relative', date=lower_date, rel=-1)
                text = 'Лог за %s\n' % (lower_date.strftime('%B'))
                for item in c.execute('''select c_id, u_id, comment, value, date, members 
                from cost where date > ? and date < ? order by date desc''', (lower_date, upper_date)).fetchall():
                    (m_cid, m_uid, m_com, m_val, m_dat, m_mem) = item
                    m_name = c.execute('select name from user where u_id = ?', (m_uid,)).fetchone()[0]
                    text = text + '#%s [%s] %sр(|%s) - %s \t(%s)\n' % (m_cid, m_name, m_val, m_mem, m_com, m_dat)
                bot.send_message(message.chat.id, text)
        elif message.text.split()[1] in ['-a', '--all']:
            text = 'Полный лог:\n'
            for item in c.execute('''select c_id, u_id, comment, value, date, members from cost 
                                    order by date desc''').fetchall():
                (m_cid, m_uid, m_com, m_val, m_dat, m_mem) = item
                m_name = c.execute('select name from user where u_id = ?', (m_uid,)).fetchone()[0]
                text = text + '#%s [%s] %sр(|%s) - %s \t(%s)\n' % (m_cid, m_name, m_val, m_mem, m_com, m_dat)
                for split in c.execute('''select u_id, proc, fin_value from split 
                                            where c_id == ?''', str(m_cid)).fetchall():
                    (s_uid, s_prc, s_val) = split
                    s_name = c.execute('select name from user where u_id = ?', (s_uid,)).fetchone()[0]
                    text = text + '╚═%.f%% (%sр) - %s\n' % (s_prc*100, s_val, s_name)
            bot.send_message(message.chat.id, text)


# bot.set_update_listener(listener)
bot.polling()
