import 'package:flutter/material.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

Future<void> main() async {
  await SentryFlutter.init(
    (o) {
      o.dsn = 'https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567';
      o.tracesSampleRate = 1.0;
    },
    appRunner: () => runApp(SentryWidget(child: MyApp())),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(home: Scaffold(body: Center(child: Text('Hello'))));
  }
}
