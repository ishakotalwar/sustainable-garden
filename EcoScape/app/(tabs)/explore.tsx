import { ScrollView, StyleSheet, Text, View } from 'react-native';

const SCORE_WEIGHTS = [
  'Native Plant Coverage: 28%',
  'Water Efficiency: 24%',
  'Pollinator Support: 16%',
  'Drought Resistance: 14%',
  'Biodiversity Mix: 10%',
  'Carbon Impact: 8%',
];

const DEMO_TIPS = [
  'Start with Irvine, CA and place 4-6 native species for the strongest score jump.',
  'Keep low-water plants dominant to improve efficiency and reduce weekly water demand.',
  'Mix species (not duplicates only) to improve biodiversity and pollinator outcomes.',
];

export default function ExploreScreen() {
  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <Text style={styles.kicker}>How The Model Works</Text>
        <Text style={styles.title}>Sustainability scoring logic for your demo.</Text>
        <Text style={styles.subtitle}>
          The Designer tab applies plant metadata in real-time each time a plant is added, moved, resized, or removed.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Plant Metadata Used</Text>
        <Text style={styles.bodyText}>Each plant stores the following attributes:</Text>
        <Text style={styles.listItem}>• Native region compatibility</Text>
        <Text style={styles.listItem}>• Water usage level</Text>
        <Text style={styles.listItem}>• Pollinator value</Text>
        <Text style={styles.listItem}>• Carbon sequestration potential</Text>
        <Text style={styles.listItem}>• Drought resistance</Text>
        <Text style={styles.listItem}>• Shade coverage potential</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Overall Score Weighting</Text>
        {SCORE_WEIGHTS.map((item) => (
          <Text key={item} style={styles.listItem}>
            • {item}
          </Text>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Demo Flow Tips</Text>
        {DEMO_TIPS.map((tip) => (
          <Text key={tip} style={styles.listItem}>
            • {tip}
          </Text>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: '#eef7ef',
  },
  content: {
    padding: 16,
    gap: 14,
  },
  hero: {
    borderRadius: 18,
    padding: 16,
    backgroundColor: '#123c2a',
  },
  kicker: {
    color: '#93deb0',
    textTransform: 'uppercase',
    fontSize: 12,
    letterSpacing: 0.8,
    fontWeight: '700',
    marginBottom: 6,
  },
  title: {
    color: '#f2fff5',
    fontSize: 24,
    fontWeight: '800',
    lineHeight: 30,
    marginBottom: 8,
  },
  subtitle: {
    color: '#c8e9d4',
    lineHeight: 20,
    fontSize: 14,
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#d8eadd',
    backgroundColor: '#ffffff',
    padding: 14,
    gap: 6,
  },
  sectionTitle: {
    fontSize: 17,
    color: '#173a2b',
    fontWeight: '700',
    marginBottom: 2,
  },
  bodyText: {
    color: '#3f5f4d',
    fontSize: 14,
    lineHeight: 20,
  },
  listItem: {
    color: '#2d4e3c',
    fontSize: 14,
    lineHeight: 20,
  },
});
