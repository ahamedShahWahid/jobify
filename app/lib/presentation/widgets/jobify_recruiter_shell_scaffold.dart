import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class JobifyRecruiterShellScaffold extends StatelessWidget {
  const JobifyRecruiterShellScaffold({required this.shell, super.key});

  final StatefulNavigationShell shell;

  static const _items = [
    NavigationDestination(
      icon: Icon(Icons.dashboard_outlined),
      selectedIcon: Icon(Icons.dashboard),
      label: 'Dashboard',
    ),
    NavigationDestination(
      icon: Icon(Icons.work_outline),
      selectedIcon: Icon(Icons.work),
      label: 'Jobs',
    ),
    NavigationDestination(
      icon: Icon(Icons.business_outlined),
      selectedIcon: Icon(Icons.business),
      label: 'Employer',
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
