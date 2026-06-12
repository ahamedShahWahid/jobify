import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_error_view.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class AsyncValueWidget<T> extends StatelessWidget {
  const AsyncValueWidget({
    required this.value,
    required this.data,
    super.key,
    this.loading,
    this.error,
    this.isEmpty,
    this.empty,
    this.onRetry,
  });

  final AsyncValue<T> value;
  final Widget Function(T data) data;

  /// Defaults to [JobifyLoadingView].
  final Widget Function()? loading;

  /// Defaults to [JobifyErrorView] wired to [onRetry].
  final Widget Function(Object e, StackTrace s)? error;

  /// Optional predicate. When true, render [empty] instead of [data].
  final bool Function(T data)? isEmpty;
  final Widget Function()? empty;

  /// Wired into the default [JobifyErrorView]'s retry button.
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return value.when(
      loading: () => (loading ?? () => const JobifyLoadingView())(),
      error: (e, s) => (error ??
          (Object err, StackTrace st) =>
              JobifyErrorView(error: err, onRetry: onRetry))(e, s),
      data: (d) {
        if (isEmpty?.call(d) ?? false) {
          return (empty ??
              () => const JobifyEmptyState(
                    headline: 'Nothing here yet',
                    body: '',
                  ))();
        }
        return data(d);
      },
    );
  }
}
