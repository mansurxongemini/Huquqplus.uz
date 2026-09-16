# Telegram Bot va Server Sozlamalari Bo'yicha Qoidalar

1. **Rootless Portlar**: Rootless konteyner muhitlarida har doim 1024 dan yuqori portlardan foydalaning (masalan, 8000). Ngrok va boshqa tunnellarni ham aynan shu portga bog'lang.
2. **Guruh Moderatsiyasi**: Guruhdagi xabarlar ostiga faqat adminga tegishli maxsus inline tugmalar qo'ymang. Buning o'rniga Reply orqali ishlovchi admin komandalari (`/block`, `/unblock`) dan foydalaning.
