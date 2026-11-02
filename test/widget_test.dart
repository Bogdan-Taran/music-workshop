import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:music_workshop/main.dart';

void main() {
  testWidgets('navigation switches between the three sections', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: MusicWorkshopApp()));
    await tester.pumpAndSettle();
    expect(find.text('Добавить ссылки'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.music_note_outlined));
    await tester.pumpAndSettle();
    expect(find.text('Здесь появятся ваши треки'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();
    expect(find.text('Аккаунт Яндекса'), findsOneWidget);
  });
}
