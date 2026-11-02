import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/app.dart';

final queueProvider = NotifierProvider<QueueViewModel, List<Uri>>(QueueViewModel.new);
class QueueViewModel extends Notifier<List<Uri>> {
  @override List<Uri> build() => [];
  int add(String input) {
    final existing = state.toSet();
    final valid = <Uri>[];
    for (final line in input.split(RegExp(r'\s+'))) {
      final uri = Uri.tryParse(line.trim());
      if (uri != null && (uri.scheme == 'https' || uri.scheme == 'http') && uri.host.isNotEmpty && existing.add(uri)) valid.add(uri);
    }
    state = [...state, ...valid];
    return valid.length;
  }
  void remove(Uri uri) => state = state.where((item) => item != uri).toList();
}
class DownloadsPage extends ConsumerStatefulWidget {
  const DownloadsPage({super.key});
  @override ConsumerState<DownloadsPage> createState() => _DownloadsPageState();
}
class _DownloadsPageState extends ConsumerState<DownloadsPage> {
  final controller = TextEditingController();
  @override void dispose() { controller.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) {
    final queue = ref.watch(queueProvider);
    return PageLayout(title: 'Скачивание', subtitle: 'Соберите любимые треки в одном месте.', children: [
      Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Добавить ссылки', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)), const SizedBox(height: 10), const Text('YouTube или Яндекс Музыка · одна ссылка на строку', style: TextStyle(color: muted, fontSize: 12)), const SizedBox(height: 12),
        TextField(controller: controller, maxLines: 3, decoration: const InputDecoration(hintText: 'Вставьте ссылки на треки сюда…', hintStyle: TextStyle(color: muted, fontSize: 14))), const SizedBox(height: 12),
        SizedBox(width: double.infinity, child: FilledButton(onPressed: () { final count = ref.read(queueProvider.notifier).add(controller.text); if (count > 0) controller.clear(); ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(count > 0 ? 'Добавлено ссылок: $count' : 'Не найдено новых ссылок'))); }, child: const Text('Добавить в очередь'))),
        const SizedBox(height: 8), SizedBox(width: double.infinity, child: OutlinedButton(onPressed: () async { final data = await Clipboard.getData('text/plain'); if (data?.text != null) controller.text = data!.text!; }, child: const Text('Вставить из буфера'))),
      ])), const SizedBox(height: 12),
      Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [const Text('Очередь', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)), const Spacer(), Text('${queue.length} треков', style: const TextStyle(color: muted, fontSize: 12))]),
        if (queue.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 35), child: Center(child: Column(children: [Icon(Icons.album_outlined, color: orange, size: 52), SizedBox(height: 12), Text('Здесь появятся ваши треки', style: TextStyle(fontWeight: FontWeight.bold)), SizedBox(height: 8), Text('Добавьте ссылки выше, чтобы начать загрузку', textAlign: TextAlign.center, style: TextStyle(color: muted, fontSize: 12))])))
        else ...queue.map((uri) => ListTile(contentPadding: EdgeInsets.zero, title: Text(uri.host), subtitle: Text(uri.toString(), maxLines: 1, overflow: TextOverflow.ellipsis), trailing: IconButton(icon: const Icon(Icons.close), onPressed: () => ref.read(queueProvider.notifier).remove(uri)))),
      ])), const SizedBox(height: 16), const Text('Папка загрузок', style: TextStyle(color: muted, fontSize: 12)), const SizedBox(height: 6), const Text('Выбор папки пока недоступен'), const SizedBox(height: 12),
      const SizedBox(width: double.infinity, child: FilledButton(onPressed: null, child: Text('Начать скачивание'))), const SizedBox(height: 8), const Text('Загрузка будет доступна после подключения сервисов.', style: TextStyle(color: muted, fontSize: 12)),
    ]);
  }
}
