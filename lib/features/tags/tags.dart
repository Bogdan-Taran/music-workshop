import 'package:flutter/material.dart';
import '../../core/app.dart';
class TagsPage extends StatelessWidget {
  const TagsPage({super.key});
  @override Widget build(BuildContext context) => const PageLayout(title: 'Теги и обложки', subtitle: 'Изменяйте метаданные и сохраняйте новые копии файлов.', children: [
    Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Треки', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)), SizedBox(height: 36), Center(child: Icon(Icons.library_music_outlined, color: orange, size: 48)), SizedBox(height: 16), Center(child: Text('Здесь появятся ваши треки')), SizedBox(height: 10), Center(child: Text('Выбор файлов и редактирование пока недоступны.', textAlign: TextAlign.center, style: TextStyle(color: muted))), SizedBox(height: 32)])),
  ]);
}
