import os
from typing import Callable, Optional, TypeVar

import redis
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from messages import (
    INTRO_MESSAGES,
    NEW_INTENTION_KEYBOARD,
    READY_KEYBOARD,
    READY_MESSAGE,
)
from regexes import parse_anon_intention, parse_named_intention
from state import BotState

load_dotenv()


T = TypeVar("T")


def require_env(name: str, cast: Callable[[str], T] = str) -> T:
    value = os.getenv(name)

    if value is None:
        raise RuntimeError(f"Env var {name} is not set")

    try:
        return cast(value)
    except Exception as e:
        raise RuntimeError(
            f"Env var {name} must be {cast.__name__}, got {value!r}"
        ) from e


BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN")
ACTIVATION_PASSWORD = require_env("ACTIVATION_PASSWORD")
REDIS_HOST = require_env("REDIS_HOST")
REDIS_PORT = require_env("REDIS_PORT", int)


redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
state = BotState(redis_client)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat is None or chat.type != "private":
        return

    for text in INTRO_MESSAGES:
        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode="HTML")

    await context.bot.send_message(
        chat_id=chat.id,
        text=READY_MESSAGE,
        parse_mode="HTML",
        reply_markup=READY_KEYBOARD,
    )


async def show_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    chat = query.message.chat if query.message else None
    if chat is None or chat.type != "private":
        return

    for text in INTRO_MESSAGES:
        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode="HTML")


async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        return

    message = update.message
    if message is None or message.text is None:
        return

    chat = message.chat
    if chat.type != "private":
        return

    if message.text.startswith("/"):
        return

    # TODO: verificar se usuário está banido

    pending_intention = context.user_data.get("pending_intention")
    if pending_intention is not None:
        await message.reply_text(
            "Confirme ou cancele sua última intenção antes de escrever uma nova. Ou então, selecione o botão abaixo.",
            reply_markup=NEW_INTENTION_KEYBOARD,
        )
        return

    processed_intention = None

    parsed = parse_named_intention(message.text)
    if parsed is not None:
        processed_intention = (
            f"Nome: {parsed['name']}\n\nIntenção: {parsed['intention']}"
        )
    else:
        parsed = parse_anon_intention(message.text)
        processed_intention = f"Intenção anônima: {parsed}"

    context.user_data["pending_intention"] = processed_intention

    confirmation_text = (
        "Vou enviar sua intenção da seguinte forma. Confirma?\n\n"
        f"<pre>{processed_intention}</pre>"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm_send"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_send"),
            ]
        ]
    )

    await message.reply_text(
        confirmation_text, reply_markup=keyboard, parse_mode="HTML"
    )


async def handle_confirmation_buttons(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if context.user_data is None:
        return

    query = update.callback_query
    if query is None or query.message is None:
        return

    await query.answer()

    data = query.data
    intention = context.user_data.get("pending_intention")

    # TODO: verificar se usuário está banido

    if intention is None:
        await query.edit_message_text("⚠️ Não há intenção pendente para enviar.")
        return

    if data == "confirm_send":
        outbox_chat_id = state.get_outbox_chat_id()
        if outbox_chat_id is None:
            await context.bot.send_message(
                query.message.chat.id,
                "💀 Desculpe, no momento não estou ativado. Reclame com os admins!",
            )
            return

        await context.bot.send_message(chat_id=outbox_chat_id, text=intention)
        context.user_data.pop("pending_intention", None)

        await query.edit_message_text(
            f"<pre>{intention}</pre>\n\n—\n\n📨 Essa intenção foi enviada, agora é só aguardar.",
            reply_markup=NEW_INTENTION_KEYBOARD,
            parse_mode="HTML",
        )

        return

    if data == "cancel_send":
        await query.edit_message_text(
            f"<pre>{intention}</pre>\n\n—\n\n❌ Essa intenção foi cancelada.",
            reply_markup=NEW_INTENTION_KEYBOARD,
            parse_mode="HTML",
        )
        context.user_data.pop("pending_intention", None)
        return


async def handle_new_intention_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if context.user_data is None:
        return

    query = update.callback_query
    if query is None or query.message is None:
        return

    await query.answer()

    context.user_data.pop("pending_intention", None)
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=READY_MESSAGE,
        parse_mode="HTML",
        reply_markup=READY_KEYBOARD,
    )


async def on_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member is None:
        return

    new_status = update.my_chat_member.new_chat_member.status
    if new_status in ("member", "administrator"):
        await context.bot.send_message(
            chat_id=update.my_chat_member.chat.id, text="Qual é a senha?"
        )


async def handle_password_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global outbox_chat_id

    message = update.message
    if message is None or message.chat.type not in ("group", "supergroup"):
        return

    if message.reply_to_message is None:
        return

    replied_to = message.reply_to_message

    if (
        replied_to.from_user is None
        or not replied_to.from_user.is_bot
        or replied_to.from_user.id != context.bot.id
    ):
        return

    chat_id = message.chat.id
    outbox_chat_id = state.get_outbox_chat_id()

    if outbox_chat_id == chat_id:
        return

    if message.text != ACTIVATION_PASSWORD:
        await message.reply_text("Senha incorreta.")
        return

    if outbox_chat_id is not None:
        await context.bot.send_message(
            chat_id=outbox_chat_id,
            text="Fui desvinculado deste grupo. Envie a senha novamente para me ativar aqui.",
        )

    state.set_outbox_chat_id(chat_id)
    await message.reply_text("Ativado. Vou encaminhar as intenções pra cá.")


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        CallbackQueryHandler(show_instructions, pattern="^instructions$")
    )

    application.add_handler(
        ChatMemberHandler(on_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_password_reply)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_message)
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_confirmation_buttons, pattern="^(confirm|cancel)_send$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(handle_new_intention_button, pattern="^new_intention$")
    )

    print("ANONYMOUS INTENTIONS BOT: Ready")
    application.run_polling()


if __name__ == "__main__":
    main()
