import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/data/notifications/notifications_repository.dart';
import 'package:kpa_app/data/notifications/notifications_repository_impl.dart';
import 'package:kpa_app/presentation/notifications/notifications_screen.dart';

NotificationDto _n(String id, {DateTime? readAt}) => NotificationDto(
      id: id,
      kind: 'application_received',
      channel: 'in_app',
      status: 'sent',
      payload: const {'job_title': 'Engineer', 'employer_name': 'Acme'},
      sendAfter: DateTime(2026),
      readAt: readAt,
      createdAt: DateTime(2026),
    );

class _Repo implements NotificationsRepository {
  final List<String> marked = [];
  @override
  Future<NotificationsPageDto> fetchPage(
          {String? cursor, int limit = 20}) async =>
      NotificationsPageDto(
        items: [NotificationListItemDto(notification: _n('n1'))],
        nextCursor: null,
      );
  @override
  Future<NotificationDto> markRead(String id) async {
    marked.add(id);
    return _n(id, readAt: DateTime(2026, 2));
  }
}

void main() {
  testWidgets('renders friendly title + marks read on tap', (tester) async {
    final repo = _Repo();
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => const NotificationsScreen()),
    ]);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [notificationsRepositoryProvider.overrideWithValue(repo)],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(
        find.text('Application received for Engineer at Acme'), findsOneWidget);

    await tester.tap(find.text('Application received for Engineer at Acme'));
    await tester.pumpAndSettle();
    expect(repo.marked, ['n1']);
  });
}
