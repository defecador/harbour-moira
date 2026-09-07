TARGET = harbour-moira
CONFIG += sailfishapp c++11

# Extraction is Python under pyotherside and playback is driven from QML,
# so the C++ side is just the launcher.
SOURCES += src/main.cpp

DISTFILES += \
    qml/harbour-moira.qml \
    qml/cover/CoverPage.qml \
    qml/pages/SearchPage.qml \
    qml/pages/VideoPage.qml \
    qml/components/Extractor.qml \
    qml/components/StreamThumbnail.qml \
    rpm/harbour-moira.spec

# The Python extraction service ships as data, not as compiled code.
python.files = python
python.path = /usr/share/$${TARGET}
INSTALLS += python

SAILFISHAPP_ICONS = 86x86 108x108 128x128 172x172

CONFIG += sailfishapp_i18n
TRANSLATIONS += translations/harbour-moira-fi.ts
