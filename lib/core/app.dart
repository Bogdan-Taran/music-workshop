import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../features/downloads/downloads.dart';
import '../features/tags/tags.dart';
import '../features/account/account.dart';

const orange = Color(0xffff681f);
const muted = Color(0xff929197);
const panel = Color(0xff1b1b20);
final workshopTheme = ThemeData(
  useMaterial3: true,
  fontFamily: 'Roboto',
  scaffoldBackgroundColor: const Color(0xff101012),
  colorScheme: ColorScheme.fromSeed(seedColor: orange, brightness: Brightness.dark, surface: panel),
  textTheme: ThemeData.dark().textTheme.apply(fontFamily: 'Roboto'),
  filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(backgroundColor: orange, foregroundColor: Colors.white, minimumSize: const Size(0, 46), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)))),
  inputDecorationTheme: InputDecorationTheme(filled: true, fillColor: const Color(0xff101012), border: OutlineInputBorder(borderRadius: BorderRadius.circular(9), borderSide: const BorderSide(color: Color(0xff34343b))), enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(9), borderSide: const BorderSide(color: Color(0xff34343b)))),
);
final router = GoRouter(initialLocation: '/downloads', routes: [
  ShellRoute(builder: (context, state, child) => AppShell(location: state.uri.path, child: child), routes: [
    GoRoute(path: '/downloads', builder: (_, _) => const DownloadsPage()),
    GoRoute(path: '/tags', builder: (_, _) => const TagsPage()),
    GoRoute(path: '/account', builder: (_, _) => const AccountPage()),
  ]),
]);
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child, required this.location});
  final Widget child;
  final String location;
  @override
  Widget build(BuildContext context) {
    final index = location.startsWith('/tags') ? 1 : location.startsWith('/account') ? 2 : 0;
    void navigate(int i) => context.go(['/downloads', '/tags', '/account'][i]);
    const destinations = [NavigationDestination(icon: Icon(Icons.download_outlined), label: 'Скачивание'), NavigationDestination(icon: Icon(Icons.music_note_outlined), label: 'Теги и обложки'), NavigationDestination(icon: Icon(Icons.person_outline), label: 'Аккаунт')];
    return LayoutBuilder(builder: (context, constraints) {
      final wide = constraints.maxWidth >= 700;
      return Scaffold(
        bottomNavigationBar: wide ? null : NavigationBar(selectedIndex: index, onDestinationSelected: navigate, backgroundColor: const Color(0xff151518), indicatorColor: const Color(0xff40271f), destinations: destinations),
        body: SafeArea(child: Row(children: [
          if (wide) NavigationRail(extended: constraints.maxWidth >= 1000, selectedIndex: index, onDestinationSelected: navigate, backgroundColor: const Color(0xff151518), indicatorColor: const Color(0xff40271f), destinations: const [NavigationRailDestination(icon: Icon(Icons.download_outlined), label: Text('Скачивание')), NavigationRailDestination(icon: Icon(Icons.music_note_outlined), label: Text('Теги и обложки')), NavigationRailDestination(icon: Icon(Icons.person_outline), label: Text('Аккаунт'))]),
          Expanded(child: child),
        ])),
      );
    });
  }
}
class PageLayout extends StatelessWidget {
  const PageLayout({super.key, required this.title, required this.subtitle, required this.children});
  final String title, subtitle;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => SingleChildScrollView(padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20), child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1120), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Row(children: [Icon(Icons.album, color: orange, size: 22), SizedBox(width: 8), Text('Музыка', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)), Spacer(), Text('●  Локальная работа', style: TextStyle(color: Color(0xff6ab795), fontSize: 11))]),
    const SizedBox(height: 32), Text(title, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)), const SizedBox(height: 6), Text(subtitle, style: const TextStyle(color: muted, fontSize: 14)), const SizedBox(height: 20), ...children,
  ]))));
}
class Panel extends StatelessWidget {
  const Panel({super.key, required this.child}); final Widget child;
  @override Widget build(BuildContext context) => Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: panel, borderRadius: BorderRadius.circular(14)), child: child);
}
