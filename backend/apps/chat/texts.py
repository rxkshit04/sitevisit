"""Fixed replies for moments when the model must not be trusted to improvise."""


def t(table: dict, lang: str) -> str:
    return table.get(lang, table["en"])


HOLDING = {
    "en": "Thanks for your message. One of our team will reply shortly and help you book a visit.",
    "hi": "आपके संदेश के लिए धन्यवाद। हमारी टीम का एक सदस्य जल्द ही आपसे संपर्क करेगा और विज़िट बुक करने में मदद करेगा।",
    "gu": "તમારા સંદેશ બદલ આભાર. અમારી ટીમનો એક સભ્ય ટૂંક સમયમાં તમારો સંપર્ક કરશે અને વિઝિટ બુક કરવામાં મદદ કરશે.",
}

SAFE_FALLBACK = {
    "en": "I want to give you accurate details, so I've asked a team member to confirm this and reply.",
    "hi": "मैं आपको सही जानकारी देना चाहता हूँ, इसलिए मैंने टीम के एक सदस्य से पुष्टि करके जवाब देने को कहा है।",
    "gu": "હું તમને સાચી માહિતી આપવા માંગું છું, તેથી મેં ટીમના એક સભ્યને પુષ્ટિ કરીને જવાબ આપવા કહ્યું છે.",
}

OPT_OUT_ACK = {
    "en": "Understood. We won't message you again.",
    "hi": "ठीक है। हम आपको दोबारा संदेश नहीं भेजेंगे।",
    "gu": "સમજાયું. અમે તમને ફરી સંદેશ નહીં મોકલીએ.",
}

HANDOFF_NAMED = {
    "en": "I've passed your chat to {name} from our sales team. They'll confirm and be in touch.",
    "hi": "मैंने आपकी चैट हमारी सेल्स टीम के {name} को भेज दी है। वे पुष्टि करके आपसे संपर्क करेंगे।",
    "gu": "મેં તમારી ચેટ અમારી સેલ્સ ટીમના {name} ને મોકલી છે. તેઓ પુષ્ટિ કરીને તમારો સંપર્ક કરશે.",
}

HANDOFF_TEAM = {
    "en": "I've passed your chat to our sales team. They'll confirm and be in touch.",
    "hi": "मैंने आपकी चैट हमारी सेल्स टीम को भेज दी है। वे पुष्टि करके आपसे संपर्क करेंगे।",
    "gu": "મેં તમારી ચેટ અમારી સેલ્સ ટીમને મોકલી છે. તેઓ પુષ્ટિ કરીને તમારો સંપર્ક કરશે.",
}