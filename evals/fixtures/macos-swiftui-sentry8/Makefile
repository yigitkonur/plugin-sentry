SCHEME = MyApp

.PHONY: release
release:
	xcodebuild -scheme $(SCHEME) -configuration Release archive -archivePath build/MyApp.xcarchive
	xcodebuild -exportArchive -archivePath build/MyApp.xcarchive -exportPath build/export -exportOptionsPlist ExportOptions.plist
	xcrun notarytool submit build/export/MyApp.zip --keychain-profile notary --wait
	hdiutil create -volname MyApp -srcfolder build/export build/MyApp.dmg
