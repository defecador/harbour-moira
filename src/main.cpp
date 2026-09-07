#include <QtQuick>
#include <QGuiApplication>
#include <QQuickView>
#include <QQmlContext>
#include <sailfishapp.h>

/*
 * Nothing but the launcher lives in C++ now. Extraction is Python running
 * in-process under pyotherside, and the models it feeds are plain QML
 * ListModels - see qml/components/Extractor.qml.
 */
int main(int argc, char *argv[])
{
    QScopedPointer<QGuiApplication> app(SailfishApp::application(argc, argv));
    app->setOrganizationName(QStringLiteral("org.moira"));
    app->setApplicationName(QStringLiteral("harbour-moira"));

    QScopedPointer<QQuickView> view(SailfishApp::createView());
    view->rootContext()->setContextProperty(
        QStringLiteral("appVersion"), QStringLiteral(APP_VERSION));
    view->setSource(SailfishApp::pathToMainQml());
    view->show();

    return app->exec();
}
