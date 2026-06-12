import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/splash/bootstrap_controller.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';

class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<AsyncValue<BootstrapOutcome>>(
      bootstrapControllerProvider,
      (prev, next) {
        next.whenData((outcome) {
          final target =
              outcome == BootstrapOutcome.feed ? Routes.feed : Routes.signIn;
          context.go(target);
        });
      },
    );

    final value = ref.watch(bootstrapControllerProvider);
    return Scaffold(
      body: AsyncValueWidget<BootstrapOutcome>(
        value: value,
        data: (_) => const SizedBox.shrink(),
        onRetry: () => ref.read(bootstrapControllerProvider.notifier).retry(),
      ),
    );
  }
}
