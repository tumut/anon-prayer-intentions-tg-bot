import os
from datetime import datetime, timezone
from typing import Callable, TypeVar

import redis
from dotenv import load_dotenv
from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
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
    ADMIN_ACTIONS_MESSAGE,
    INTRO_MESSAGE,
    NEW_INTENTION_KEYBOARD,
    READY_MESSAGE,
    RULES_AND_INSTRUCTIONS_MESSAGES,
    get_admin_keyboard,
    get_instructions_keyboard,
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

    await context.bot.send_message(
        chat_id=chat.id,
        text=INTRO_MESSAGE,
        parse_mode="HTML",
        reply_markup=get_instructions_keyboard(newbie=True),
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.effective_chat is not None
    await context.bot.send_message(update.effective_chat.id, "Pong.")


async def show_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    chat = query.message.chat if query.message else None
    if chat is None or chat.type != "private":
        return

    first_message_id = None

    for text in RULES_AND_INSTRUCTIONS_MESSAGES:
        m = await context.bot.send_message(
            chat_id=chat.id, text=text, parse_mode="HTML"
        )
        if first_message_id is None:
            first_message_id = m.id

    data = query.data
    assert data is not None
    is_newbie = ":newbie" in data

    text = None

    if is_newbie:
        text = (
            "☝️ Leia tudo a partir daqui. Quando terminar, é só apertar no botão abaixo."
        )
    else:
        text = "☝️ Leia a partir daqui."

    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        reply_markup=NEW_INTENTION_KEYBOARD,
        reply_to_message_id=first_message_id,
    )


async def is_banned_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None:
        # Silent failure; I expect this to never happen
        return True

    user_id = update.effective_user.id
    ban_token = state.get_ban_token_by_user(user_id)

    if ban_token is None:
        return False

    notification = (
        "Você está banido e não pode usar o bot. Fale com um admin e mostre o código abaixo.\n\n"
        f"<code>{ban_token}</code>\n\n"
        "Para mais informações use o comando: /baninfo"
    )

    if update.effective_message is None:
        await context.bot.send_message(
            chat_id=user_id, text=notification, parse_mode="HTML"
        )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=notification,
            parse_mode="HTML",
            reply_to_message_id=update.effective_message.id,
        )

    return True


async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned_and_notify(update, context):
        return

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
        confirmation_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        reply_to_message_id=message.id,
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

    if await is_banned_and_notify(update, context):
        return

    data = query.data
    intention = context.user_data.get("pending_intention")

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

        await context.bot.send_message(
            chat_id=outbox_chat_id,
            text=intention,
            reply_markup=get_admin_keyboard(query.message.chat.id),
        )
        context.user_data.pop("pending_intention", None)

        await query.edit_message_text(
            f"<pre>{intention}</pre>\n\n—\n\n📨 Essa intenção foi enviada, agora é só aguardar.",
            reply_markup=NEW_INTENTION_KEYBOARD,
            parse_mode="HTML",
        )

        return

    if data == "cancel_send":
        await query.edit_message_text(
            f"❌ Essa intenção foi cancelada.",
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

    if await is_banned_and_notify(update, context):
        return

    context.user_data.pop("pending_intention", None)
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=READY_MESSAGE,
        parse_mode="HTML",
        reply_markup=get_instructions_keyboard(),
    )


async def is_inactive_group_and_notify(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_chat is None:
        # Silent failure; I expect this to never happen
        return True

    if update.effective_chat.type not in (Chat.GROUP, Chat.SUPERGROUP):
        # Normally should only end up here in case a user is trying to use admin
        # commands in private messaging; silent failure, don't acknowledge
        return True

    chat_id = update.effective_chat.id
    outbox_chat_id = state.get_outbox_chat_id()

    if outbox_chat_id == chat_id:
        return False

    text = "Não estou ativo nesse grupo. Cadê a senha?"

    if update.effective_message is None:
        await context.bot.send_message(chat_id, text)
    else:
        await context.bot.send_message(
            chat_id, text, reply_to_message_id=update.effective_message.message_id
        )

    return True


async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if (
        query is None
        or query.data is None
        or query.from_user is None
        or not isinstance(query.message, Message)
    ):
        return

    if await is_inactive_group_and_notify(update, context):
        await query.answer()
        return

    if not query.data.startswith("admin_"):
        await query.answer()
        return

    if query.data == "admin_actions":
        await context.bot.send_message(
            query.message.chat_id, text=ADMIN_ACTIONS_MESSAGE, parse_mode="HTML"
        )
        await query.answer()
        return

    if query.data.startswith("admin_feedback"):
        await query.answer(text="Use: /feedback mensagem", show_alert=False)
        return

    await query.answer()

    action, user_id_str = query.data.split(":", 1)
    intention = query.message.text

    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text(
            f"{intention}\n\n—\n\n⚠️ Erro interno (ID inválido)."
        )
        return

    if action == "admin_accept":
        await context.bot.send_message(
            chat_id=user_id,
            text=f"<pre>{intention}</pre>\n\n✅ A intenção acima foi aceita, confira se ela apareceu no canal.",
            reply_markup=NEW_INTENTION_KEYBOARD,
            parse_mode="HTML",
        )

        await query.edit_message_reply_markup(None)
        await query.message.reply_text(
            f"✅ Intenção aceita por {query.from_user.first_name}.\n\n"
            "(Vocês precisarão copiar e colar as intenções enquanto o bot ainda não for vinculado ao canal.)"
        )


def retrieve_intention_sender_id(intention_msg: Message) -> int | None:
    if intention_msg.reply_markup is not None:
        for row in intention_msg.reply_markup.inline_keyboard:
            for button in row:
                if isinstance(button.callback_data, str):
                    return int(button.callback_data.split(":", 1)[1])
                break
            break

    return None


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_inactive_group_and_notify(update, context):
        return

    if update.message is None:
        return

    if update.message.from_user is None:
        return

    if not context.args:
        await update.message.reply_text("Você precisa fornecer um motivo.")
        return

    if update.message.reply_to_message is None:
        await update.message.reply_text(
            "Você deve responder à mensagem com a intenção."
        )
        return

    intention_msg = update.message.reply_to_message
    intention_sender_id = retrieve_intention_sender_id(intention_msg)

    if intention_sender_id is None or intention_msg.text is None:
        await update.message.reply_text(
            "Não posso fazer isso com a mensagem que você respondeu."
        )
        return

    intention = intention_msg.text
    reason = " ".join(context.args)
    admin_name = update.message.from_user.first_name

    await intention_msg.edit_text(
        f"{intention}\n\n—\n\n❌ Intenção rejeitada por {admin_name}. Motivo: <i>{reason}</i>",
        parse_mode="HTML",
    )

    await context.bot.send_message(
        chat_id=intention_sender_id,
        text=f"<pre>{intention}</pre>\n\n❌ A intenção acima foi rejeitada.\n\nMotivo: <i>{reason}</i>",
        parse_mode="HTML",
    )

    await update.message.reply_text(
        "A intenção foi ❌rejeitada e o remetente dela foi notificado com o motivo fornecido."
    )


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_inactive_group_and_notify(update, context):
        return

    if update.message is None:
        return

    if update.message.from_user is None:
        return

    if not context.args:
        await update.message.reply_text("Você precisa fornecer um motivo.")
        return

    if update.message.reply_to_message is None:
        await update.message.reply_text(
            "Você deve responder à mensagem com a intenção."
        )
        return

    intention_msg = update.message.reply_to_message
    intention_sender_id = retrieve_intention_sender_id(intention_msg)

    if intention_sender_id is None or intention_msg.text is None:
        await update.message.reply_text(
            "Não posso fazer isso com a mensagem que você respondeu."
        )
        return

    intention = intention_msg.text
    reason = " ".join(context.args)
    admin_id = update.message.from_user.id
    admin_name = update.message.from_user.first_name

    _, ban_token = state.ban_user(intention_sender_id, reason, intention, admin_id)

    await intention_msg.edit_text(
        f"{intention}\n\n—\n\n🔨 O remetente desta intenção foi banido por {admin_name}. Motivo: <i>{reason}</i>\n\n<code>{ban_token}</code>\n\n",
        parse_mode="HTML",
    )

    ban_message = (
        f"<pre>{intention}</pre>\n\n"
        "🔨 Você foi banido por causa da intenção acima.\n\n"
        f"Motivo: <i>{reason}</i>\n\n"
        "Se quiser contestar esse banimento, fale com algum admin pessoalmente. "
        "Encaminhe para o admin esta mensagem, ele precisará do código abaixo para te desbanir.\n\n"
        f"<code>{ban_token}</code>"
    )

    await context.bot.send_message(
        chat_id=intention_sender_id,
        text=ban_message,
        parse_mode="HTML",
    )

    await update.message.reply_text(
        (
            "O remetente da intenção foi 🔨banido e ele foi notificado com o motivo fornecido. "
            "Para desbani-lo, use o token abaixo e o comando /unban.\n\n"
            f"<code>{ban_token}</code>"
        ),
        parse_mode="HTML",
    )


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_inactive_group_and_notify(update, context):
        return

    if update.effective_chat is None or update.effective_message is None:
        return

    group_id = update.effective_chat.id
    message_id = update.effective_message.id

    if not context.args:
        await context.bot.send_message(
            chat_id=group_id, text="Forneça o código.", reply_to_message_id=message_id
        )
        return

    ban_token = context.args[0]
    response = None

    if state.unban_user(ban_token):
        response = "O usuário foi desbanido. Se possível, o avise, pois não guardo os ID's de usuários banidos e não tenho como notificá-lo."
    else:
        response = "Esse código não corresponde a nenhum usuário banido."

    await context.bot.send_message(
        chat_id=group_id,
        text=response,
        reply_to_message_id=message_id,
    )


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_inactive_group_and_notify(update, context):
        return

    if update.message is None:
        return

    if update.message.from_user is None:
        return

    if not context.args:
        await update.message.reply_text(
            "Você precisa escrever uma mensagem pro usuário."
        )
        return

    if update.message.reply_to_message is None:
        await update.message.reply_text(
            "Você deve responder à mensagem com a intenção."
        )
        return

    intention_msg = update.message.reply_to_message
    intention_sender_id = retrieve_intention_sender_id(intention_msg)

    if intention_sender_id is None or intention_msg.text is None:
        await update.message.reply_text(
            "Não posso fazer isso com a mensagem que você respondeu."
        )
        return

    intention = intention_msg.text
    feedback_text = " ".join(context.args)

    ban_message = (
        f"<pre>{intention}</pre>\n\n"
        "📢 Um admin te enviou uma mensagem referente à intenção acima. Leia:\n\n"
        f"<i>{feedback_text}</i>"
    )

    await context.bot.send_message(
        chat_id=intention_sender_id,
        text=ban_message,
        parse_mode="HTML",
    )

    await update.message.reply_text("📨 Mensagem enviada!")


def format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


async def baninfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None or update.effective_message is None:
        return

    reply_to_id = update.effective_message.id

    if update.effective_chat.type in (Chat.GROUP, Chat.SUPERGROUP):
        # We're in a group, so it should only be used by admins
        if await is_inactive_group_and_notify(update, context):
            return

        group_id = update.effective_chat.id

        if not context.args:
            await context.bot.send_message(
                group_id, "Forneça o código.", reply_to_message_id=reply_to_id
            )
            return

        ban_token = context.args[0]
        ban_info = state.get_ban_info_by_ban_token(ban_token)

        response = None

        if ban_info is None:
            response = "Esse código não corresponde a nenhum usuário banido."
        else:
            timestamp = format_timestamp(float(ban_info["timestamp"]))
            intention = ban_info["intention"]
            reason = ban_info["reason"]

            response = (
                f"Quando: <code>{timestamp}</code>\n\n"
                "Intenção:\n\n"
                f"<pre>{intention}</pre>\n\n"
                "Motivo:\n\n"
                f"<pre>{reason}</pre>\n\n"
                f"<code>{ban_token}</code>"
            )

        await context.bot.send_message(
            group_id,
            response,
            parse_mode="HTML",
            reply_to_message_id=reply_to_id,
        )
    else:
        # Private messages
        assert update.effective_user

        user_id = update.effective_user.id
        ban_token = state.get_ban_token_by_user(user_id)

        if ban_token is None:
            await context.bot.send_message(
                user_id,
                "Você não está banido. :)",
                reply_to_message_id=reply_to_id,
            )
            return

        ban_info = state.get_ban_info_by_ban_token(ban_token)
        assert ban_info is not None

        timestamp = format_timestamp(float(ban_info["timestamp"]))
        intention = ban_info["intention"]
        reason = ban_info["reason"]

        description = (
            f"Quando: <code>{timestamp}</code>\n\n"
            "Intenção:\n\n"
            f"<pre>{intention}</pre>\n\n"
            "Motivo:\n\n"
            f"<pre>{reason}</pre>\n\n"
            "Apresente o código abaixo a um admin para contestar seu banimento. "
            "De preferência, encaminhe essa mensagem.\n\n"
            f"<code>{ban_token}</code>"
        )

        await context.bot.send_message(
            user_id,
            description,
            parse_mode="HTML",
            reply_to_message_id=reply_to_id,
        )


async def on_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member is None:
        return

    new_status = update.my_chat_member.new_chat_member.status
    if (
        new_status in ("member", "administrator")
        and update.effective_chat is not None
        and update.effective_chat.type in (Chat.GROUP, Chat.SUPERGROUP)
    ):
        group_id = update.my_chat_member.chat.id
        if group_id == state.get_outbox_chat_id():
            await context.bot.send_message(
                chat_id=group_id, text="Opa, estou de volta."
            )
        else:
            await context.bot.send_message(chat_id=group_id, text="Qual é a senha?")


async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global outbox_chat_id

    message = update.message
    if (
        message is None
        or message.text is None
        or message.chat.type not in ("group", "supergroup")
    ):
        return

    # We only want to deal with replies to the bot

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

    if outbox_chat_id != chat_id:
        # This comes NOT from the group we're active in, so we only care about
        # the activation password.
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

    # No guards
    application.add_handler(CommandHandler("start", start))

    # No guards
    application.add_handler(CommandHandler("ping", ping))

    # Guard against: inactive group
    application.add_handler(CommandHandler("reject", reject))

    # Guard against: inactive group
    application.add_handler(CommandHandler("ban", ban))

    # Guard against: inactive group
    application.add_handler(CommandHandler("unban", unban))

    # Guard against: inactive group
    application.add_handler(CommandHandler("feedback", feedback))

    # No guards if called in private messages
    # In group, guard against: inactive group
    application.add_handler(CommandHandler("baninfo", baninfo))

    # No guards
    application.add_handler(
        CallbackQueryHandler(show_instructions, pattern="^instructions")
    )

    # No guards
    application.add_handler(
        ChatMemberHandler(on_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    # Guard against: inactive group (done manually)
    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_messages)
    )

    # Guard against: banned users
    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_message)
    )

    # Guard against: banned users
    application.add_handler(
        CallbackQueryHandler(
            handle_confirmation_buttons, pattern="^(confirm|cancel)_send$"
        )
    )

    # Guard against: inactive group
    application.add_handler(
        CallbackQueryHandler(handle_admin_buttons, pattern="^admin_")
    )

    # Guard against: banned users
    application.add_handler(
        CallbackQueryHandler(handle_new_intention_button, pattern="^new_intention$")
    )

    print("ANONYMOUS INTENTIONS BOT: Ready")
    application.run_polling()


if __name__ == "__main__":
    main()
