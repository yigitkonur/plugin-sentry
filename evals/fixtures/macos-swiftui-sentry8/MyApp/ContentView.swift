import SwiftUI
import Sentry

struct ContentView: View {
    var body: some View {
        SentryTracedView("ContentView", waitForFullDisplay: true) {
            VStack { Text("MyApp"); Button("Export") { try? export() } }.padding()
        }
    }

    func export() throws { throw CocoaError(.fileWriteUnknown) }
}
