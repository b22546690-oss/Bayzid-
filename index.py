from flask import Flask, request
import telebot
import os

# আপনার বটের টোকেন এখানে দিন বা এনভায়রনমেন্ট ভেরিয়েবল থেকে নিন
TOKEN = os.getenv("8715509395:AAGQP3H4dWZNkYfcKzHHdylzVAF3YFZ-3gQ")
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# ডামি ডাটাবেস (রিয়েল প্রোজেক্টে MongoDB ব্যবহার করবেন)
users = {}

@app.route('/', methods=['GET'])
def index():
    return "Bot is running..."

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK', 200

# Start Command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    referrer_id = message.text.split()[1] if len(message.text.split()) > 1 else None

    if user_id not in users:
        users[user_id] = {'balance': 0, 'referrals': 0}
        if referrer_id and referrer_id in users and referrer_id != user_id:
            users[referrer_id]['balance'] += 5  # প্রতি রেফারে ৫ টাকা
            users[referrer_id]['referrals'] += 1
            bot.send_message(referrer_id, f"আপনার লিঙ্কে কেউ জয়েন করেছে! আপনি ৫ টাকা পেয়েছেন।")

    msg = (f"স্বাগতম! আমাদের ইনকাম বটে।\n\n"
           f"আপনার ব্যালেন্স: {users[user_id]['balance']} টাকা\n"
           f"আপনার রেফার লিঙ্ক: https://t.me/{(bot.get_me()).username}?start={user_id}")
    
    bot.reply_to(message, msg)

# Balance Command
@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = str(message.from_user.id)
    bal = users.get(user_id, {'balance': 0})['balance']
    bot.reply_to(message, f"আপনার বর্তমান ব্যালেন্স: {bal} টাকা")

# Withdraw Command
@bot.message_handler(commands=['withdraw'])
def withdraw(message):
    bot.reply_to(message, "টাকা তুলতে অ্যাডমিনের সাথে যোগাযোগ করুন অথবা মিনিমাম ২০ টাকা করুন।")

if __name__ == "__main__":
    app.run(debug=True)
