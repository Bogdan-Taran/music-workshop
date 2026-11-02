import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/app.dart';

void main() => runApp(const ProviderScope(child: MusicWorkshopApp()));

class MusicWorkshopApp extends StatelessWidget {
  const MusicWorkshopApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp.router(
    title: 'Музыкальная мастерская',
    debugShowCheckedModeBanner: false,
    locale: const Locale('ru'),
    supportedLocales: const [Locale('ru')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    theme: workshopTheme,
    routerConfig: router,
  );
}
