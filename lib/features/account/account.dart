import 'package:flutter/material.dart';
import '../../core/app.dart';
class AccountPage extends StatelessWidget {
  const AccountPage({super.key});
  @override Widget build(BuildContext context) => const PageLayout(title: 'Аккаунт Яндекса', subtitle: 'Управляйте подключением к Яндекс Музыке.', children: [
    Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [CircleAvatar(backgroundColor: Color(0xff40271f), child: Text('Я', style: TextStyle(color: orange, fontWeight: FontWeight.bold))), SizedBox(width: 12), Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Яндекс Музыка', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)), Text('Аккаунт не подключён', style: TextStyle(color: muted, fontSize: 12))])]), SizedBox(height: 28), Text('Подключите аккаунт в три шага', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)), SizedBox(height: 18), Text('1. Получите код для входа'), SizedBox(height: 14), Text('2. Введите код на странице Яндекса'), SizedBox(height: 14), Text('3. Вернитесь в приложение'), SizedBox(height: 24), SizedBox(width: double.infinity, child: FilledButton(onPressed: null, child: Text('Получить код'))), SizedBox(height: 8), Text('Подключение аккаунта пока недоступно.', style: TextStyle(color: muted, fontSize: 12))])),
  ]);
}
