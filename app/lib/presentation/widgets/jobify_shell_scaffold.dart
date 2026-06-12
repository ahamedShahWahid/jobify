import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class JobifyShellScaffold extends StatelessWidget {
  const JobifyShellScaffold({required this.shell, super.key});

  final StatefulNavigationShell shell;

  static const _items = [
    NavigationDestination(
      icon: Icon(Icons.search),
      label: 'Feed',
    ),
    NavigationDestination(
      icon: Icon(Icons.bookmark_outline),
      selectedIcon: Icon(Icons.bookmark),
      label: 'Saved',
    ),
    NavigationDestination(
      icon: Icon(Icons.assignment_outlined),
      selectedIcon: Icon(Icons.assignment),
      label: 'Applications',
    ),
    NavigationDestination(
      icon: Icon(Icons.person_outline),
      selectedIcon: Icon(Icons.person),
      label: 'Profile',
    ),
  ];

  void _onTap(int i) {
    if (i == shell.currentIndex) {
      shell.goBranch(i, initialLocation: true);
    } else {
      shell.goBranch(i);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        destinations: _items,
        onDestinationSelected: _onTap,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
    );
  }
}
