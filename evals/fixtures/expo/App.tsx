import * as Sentry from "@sentry/react-native";
import { Text, View } from "react-native";

Sentry.init({ dsn: process.env.EXPO_PUBLIC_SENTRY_DSN, tracesSampleRate: 1.0 });

function App() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
      <Text>Hello Expo</Text>
    </View>
  );
}

export default Sentry.wrap(App);
