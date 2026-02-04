from telegram import InlineKeyboardButton, InlineKeyboardMarkup

INTRO_MESSAGES: list[str] = [
    (
        "A paz de Cristo! Sou o bot de intenções anônimas do canal. "
        "Meu trabalho é encaminhar suas intenções anonimamente aos admins, "
        "para que eles as avaliem e postem no canal.\n\n"
        "<b>Por favor, leia atentamente as instruções abaixo.</b>"
    ),
    (
        "<b>INSTRUÇÕES DE USO DO BOT</b>\n\n"
        "1. Apenas envie uma mensagem qualquer aqui na sua conversa privada "
        "com o bot, e ela será repassada anonimamente para os admins depois da sua confirmação.\n\n"
        "2. Obs.: caso você cancele o envio de uma intenção porque quer alterar sua intenção, "
        "não edite a mensagem que você tinha enviado. Envie uma nova mensagem com as correções.\n\n"
        "3. Use um dos seguintes formatos:\n\n"
        "• Para intenções anônimas, apenas escreva o conteúdo da sua intenção. "
        'Se quiser, você pode prefixar sua mensagem com "Intenção anônima:", '
        "mas isso é inteiramente opcional. Exemplos:\n\n"
        "<pre>Pela saúde do meu pai.</pre>\n"
        "<pre>Intenção anônima: pela saúde do meu pai.</pre>\n\n"
        "• Caso você queira se identificar, use um dos seguintes formatos:\n\n"
        "<pre>Fulano - Pela saúde de Sicrano.</pre>\n"
        "<pre>Nome: Fulano\n\nIntenção: Pela saúde de Sicrano.</pre>"
    ),
    (
        "<b>REGRAS DE USO</b>\n\n"
        "1. Envie <b>apenas texto</b>. O bot não aceita imagens, áudios ou qualquer outro tipo de mídia.\n\n"
        "2. <b>Nunca coloque nomes completos</b>, a não ser que se trate de um famoso "
        "(nesse caso, especifique quem é a pessoa).\n\n"
        "3. Admins têm liberdade total de omitir detalhes da sua intenção se isso for necessário "
        "para resguardar a identidade das pessoas.\n\n"
        "4. Admins são livres para arbitrariamente rejeitar intenções, e poderão te avisar "
        "através do bot por que uma intenção foi rejeitada.\n\n"
        "5. Admins podem <b>banir</b> você, bloqueando seu acesso ao bot, caso considerem que "
        "você está fazendo mau uso dele.\n\n"
        "6. Resultarão em <b>banimento imediato</b> e estão <b>expressamente proibidas</b> intenções que contenham:\n"
        "   • Indecências.\n"
        "   • Divulgações.\n"
        "   • Pedidos de dinheiro.\n"
        "   • Importunação para com os admins.\n\n"
        "7. Caso você seja banido, os admins não saberão quem era você. "
        "Se quiser contestar o banimento, você receberá um código fornecido pelo bot."
    ),
]

READY_MESSAGE = (
    "🫡 Estou pronto para receber intenções, envie quando quiser. "
    "Eis aqui formatos prontos para copiar e colar:\n\n"
    "<pre>Intenção anônima: </pre>\n\n"
    "<pre>Nome: \n\nIntenção: </pre>"
)

ADMIN_ACTIONS_MESSAGE = (
    "Para outras ações além de aprovar, responda à mensagem da intenção com um dos seguintes comandos:\n\n"
    "/reject <code>motivo</code>\n"
    "/ban <code>motivo</code>\n"
)

READY_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("📖 Instruções & Regras", callback_data="instructions")]]
)

NEW_INTENTION_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("✍️ Nova intenção", callback_data="new_intention")]]
)
