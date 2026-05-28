import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/data/notifications/notification_dto.dart';
import 'package:kpa_app/presentation/notifications/notification_title.dart';
import 'package:kpa_app/presentation/notifications/notifications_controller.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

final _dateFormat = DateFormat.yMMMd();

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});
  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(notificationsControllerProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _onTap(NotificationDto n) async {
    await ref.read(notificationsControllerProvider.notifier).markRead(n.id);
    if (!mounted) return;
    final jobId = n.payload['job_id'];
    if (jobId is String && jobId.isNotEmpty) {
      context.go('${Routes.notifications}/jobs/$jobId');
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(notificationsControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: AsyncValueWidget<NotificationsState>(
        value: value,
        onRetry: () =>
            ref.read(notificationsControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const Center(child: Text('No notifications yet')),
        data: (s) => RefreshIndicator(
          onRefresh: () =>
              ref.read(notificationsControllerProvider.notifier).refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(KpaSpacing.lg),
            itemCount: s.items.length + 1,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                return s.isLoadingMore
                    ? const Padding(
                        padding: EdgeInsets.all(KpaSpacing.lg),
                        child: KpaLoadingView(),
                      )
                    : const SizedBox.shrink();
              }
              final n = s.items[i];
              final unread = n.readAt == null;
              return ListTile(
                leading: unread
                    ? const Icon(Icons.circle, size: 10, color: Colors.blue)
                    : const SizedBox(width: 10),
                title: Text(
                  notificationTitle(n),
                  style: TextStyle(
                    fontWeight: unread ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
                subtitle: Text(_dateFormat.format(n.createdAt)),
                onTap: () => _onTap(n),
              );
            },
          ),
        ),
      ),
    );
  }
}
