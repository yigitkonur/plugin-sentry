import * as Sentry from "@sentry/react-native";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";

Sentry.init({
  dsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
  environment: "prod",
  sendDefaultPii: true,
  tracesSampleRate: 1.0,
});

function App() {
  const [orders, setOrders] = useState<number>(0);
  useEffect(() => {
    fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/orders`)
      .then((r) => r.json())
      .then((o) => setOrders(o.length));
  }, []);
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
      <Text>{orders} orders</Text>
    </View>
  );
}

export default Sentry.wrap(App);
